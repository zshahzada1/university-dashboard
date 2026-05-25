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


if __name__ == "__main__":
    unittest.main()
