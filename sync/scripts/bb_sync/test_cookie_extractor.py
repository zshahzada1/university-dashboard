import json
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")
from cookie_extractor import extract_bb_cookies, _cdp_port, _extract_via_cdp


class TestCdpPort(unittest.TestCase):
    def test_returns_port_when_reachable(self):
        with patch("urllib.request.urlopen"):
            result = _cdp_port()
        self.assertEqual(result, 9222)

    def test_returns_none_when_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError):
            result = _cdp_port()
        self.assertIsNone(result)


class TestExtractViaCdp(unittest.TestCase):
    def _targets_response(self, ws_url="ws://127.0.0.1:9222/page/1"):
        resp = MagicMock()
        resp.read.return_value = json.dumps(
            [{"type": "page", "webSocketDebuggerUrl": ws_url}]
        ).encode()
        return resp

    def _ws_mock(self, cookies):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({"result": {"cookies": cookies}})
        return ws

    def test_returns_matching_cookies(self):
        cookies = [
            {"name": "BbRouter", "value": "abc", "domain": ".brighton.ac.uk"},
            {"name": "other", "value": "x", "domain": ".example.com"},
        ]
        ws = self._ws_mock(cookies)
        with patch("urllib.request.urlopen", return_value=self._targets_response()), \
             patch("websocket.WebSocket", return_value=ws):
            result = _extract_via_cdp("brighton.ac.uk", 9222)
        self.assertIn("BbRouter", result)
        self.assertNotIn("other", result)

    def test_raises_when_no_matching_cookies(self):
        ws = self._ws_mock([])
        with patch("urllib.request.urlopen", return_value=self._targets_response()), \
             patch("websocket.WebSocket", return_value=ws):
            with self.assertRaises(RuntimeError):
                _extract_via_cdp("brighton.ac.uk", 9222)

    def test_raises_when_websocket_client_missing(self):
        with patch.dict(sys.modules, {"websocket": None}):
            with self.assertRaises(RuntimeError):
                _extract_via_cdp("brighton.ac.uk", 9222)


class TestExtractBbCookies(unittest.TestCase):
    def test_returns_cached_cookies_when_fresh(self):
        cached = {"BbRouter": "cached"}
        mock_cache = MagicMock()
        mock_cache.exists.return_value = True
        mock_cache.stat.return_value = MagicMock(st_mtime=time.time() - 60)
        mock_cache.read_text.return_value = json.dumps(cached)
        with patch("cookie_extractor.Path", return_value=mock_cache):
            result = extract_bb_cookies(force_refresh=False)
        self.assertEqual(result["BbRouter"], "cached")

    def test_raises_when_cdp_not_reachable(self):
        mock_cache = MagicMock()
        mock_cache.exists.return_value = False
        with patch("cookie_extractor.Path", return_value=mock_cache), \
             patch("cookie_extractor._cdp_port", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                extract_bb_cookies(force_refresh=True)
        self.assertIn("debug port", str(ctx.exception))

    def test_extracts_and_caches_on_cache_miss(self):
        cookies = {"BbRouter": "fresh"}
        mock_cache = MagicMock()
        mock_cache.exists.return_value = False
        with patch("cookie_extractor.Path", return_value=mock_cache), \
             patch("cookie_extractor._cdp_port", return_value=9222), \
             patch("cookie_extractor._extract_via_cdp", return_value=cookies), \
             patch("cookie_extractor._save_cache") as mock_save:
            result = extract_bb_cookies(force_refresh=True)
        self.assertEqual(result["BbRouter"], "fresh")
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
