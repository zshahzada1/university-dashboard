import json
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

BB_WS_URL = "ws://127.0.0.1:9222/page/1"
BB_PAGE_URL = "https://studentcentral.brighton.ac.uk/webapps/portal"
OTHER_URL = "https://google.com"


def _version_mock():
    m = MagicMock()
    m.read.return_value = b"{}"
    return m


def _targets_mock(targets):
    m = MagicMock()
    m.read.return_value = json.dumps(targets).encode()
    return m


def _bb_target(ws=BB_WS_URL):
    return {"type": "page", "url": BB_PAGE_URL, "webSocketDebuggerUrl": ws}


def _other_target():
    return {"type": "page", "url": OTHER_URL, "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/2"}


class TestCdpSessionInit(unittest.TestCase):
    def test_raises_when_no_port_reachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with self.assertRaises(RuntimeError) as ctx:
                from cdp_client import CdpSession
                CdpSession()
        self.assertIn("9222", str(ctx.exception))

    def test_raises_when_no_blackboard_tab(self):
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_other_target()])
        ]):
            with self.assertRaises(RuntimeError) as ctx:
                from cdp_client import CdpSession
                CdpSession()
        self.assertIn("studentcentral.brighton.ac.uk", str(ctx.exception))

    def test_connects_to_blackboard_tab(self):
        ws = MagicMock()
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_bb_target()])
        ]), patch("websocket.WebSocket", return_value=ws):
            from cdp_client import CdpSession
            CdpSession()
        ws.connect.assert_called_once_with(BB_WS_URL, timeout=10, suppress_origin=True)

    def test_prefers_blackboard_tab_over_others(self):
        bb_ws = "ws://127.0.0.1:9222/page/2"
        ws = MagicMock()
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_other_target(), _bb_target(ws=bb_ws)])
        ]), patch("websocket.WebSocket", return_value=ws):
            from cdp_client import CdpSession
            CdpSession()
        ws.connect.assert_called_once_with(bb_ws, timeout=10, suppress_origin=True)


class TestCdpSessionFetchJson(unittest.TestCase):
    def _make_session(self):
        """Bypass __init__ to get a CdpSession with a mock WebSocket."""
        from cdp_client import CdpSession
        s = object.__new__(CdpSession)
        s._ws = MagicMock()
        s._msg_id = 0
        return s

    def _eval_response(self, status, body=None):
        return json.dumps({
            "id": 1,
            "result": {"result": {"type": "object", "value": {"status": status, "body": body}}}
        })

    def _eval_error(self, text="NetworkError"):
        return json.dumps({
            "id": 1,
            "result": {
                "result": {"type": "object", "subtype": "error", "description": text},
                "exceptionDetails": {"text": text},
            }
        })

    def test_returns_body_on_200(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(200, {"id": "u1"})
        result = s.fetch_json("/learn/api/public/v1/users/me")
        self.assertEqual(result["id"], "u1")

    def test_raises_http_error_on_401(self):
        import requests
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(401)
        with self.assertRaises(requests.HTTPError) as ctx:
            s.fetch_json("/learn/api/public/v1/users/me")
        self.assertEqual(ctx.exception.response.status_code, 401)

    def test_raises_http_error_on_404(self):
        import requests
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(404)
        with self.assertRaises(requests.HTTPError) as ctx:
            s.fetch_json("/some/path")
        self.assertEqual(ctx.exception.response.status_code, 404)

    def test_raises_runtime_error_on_js_exception(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_error("NetworkError: failed to fetch")
        with self.assertRaises(RuntimeError) as ctx:
            s.fetch_json("/learn/api/public/v1/users/me")
        self.assertIn("NetworkError", str(ctx.exception))

    def test_sends_params_embedded_in_js(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(200, {"results": []})
        s.fetch_json("/learn/api/public/v1/users/me/courses", {"limit": 200, "expand": "course"})
        sent = json.loads(s._ws.send.call_args[0][0])
        self.assertEqual(sent["method"], "Runtime.evaluate")
        self.assertIn("limit", sent["params"]["expression"])
        self.assertIn("200", sent["params"]["expression"])
        self.assertTrue(sent["params"]["awaitPromise"])


if __name__ == "__main__":
    unittest.main()
