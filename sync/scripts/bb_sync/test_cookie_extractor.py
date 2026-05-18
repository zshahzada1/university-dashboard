import json
import sys
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, '.')
from cookie_extractor import extract_bb_cookies

class TestCookieExtractor(unittest.TestCase):
    def test_returns_dict_via_cdp_when_available(self):
        """extract_bb_cookies returns cookies from CDP when it succeeds."""
        cdp_cookies = {"BbRouter": "abc123", "JSESSIONID": "xyz"}
        with patch("cookie_extractor._extract_via_cdp", return_value=cdp_cookies):
            result = extract_bb_cookies(force_refresh=True)
        self.assertIsInstance(result, dict)
        self.assertIn("BbRouter", result)
        self.assertEqual(result["BbRouter"], "abc123")

    def test_falls_back_to_browser_cookie3_when_cdp_fails(self):
        """extract_bb_cookies falls back to browser_cookie3 when CDP raises."""
        fake_cookies = json.dumps({"BbRouter": "abc123", "JSESSIONID": "xyz"})
        with patch("cookie_extractor._extract_via_cdp", side_effect=RuntimeError("CDP unavailable")), \
             patch("cookie_extractor.Path.exists", return_value=False), \
             patch("cookie_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_cookies, stderr="")
            result = extract_bb_cookies(force_refresh=True)
        self.assertIsInstance(result, dict)
        self.assertIn("BbRouter", result)

    def test_raises_when_all_methods_fail(self):
        """extract_bb_cookies raises RuntimeError when CDP and browser_cookie3 both fail."""
        with patch("cookie_extractor._extract_via_cdp", side_effect=RuntimeError("CDP unavailable")), \
             patch("cookie_extractor._WINDOWS_MANUAL_EXPORT_EXTRA_WSL", []), \
             patch("cookie_extractor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="ModuleNotFoundError: No module named 'browser_cookie3'"
            )
            with self.assertRaises(RuntimeError):
                extract_bb_cookies(force_refresh=True)

class TestExtractViaCdp(unittest.TestCase):
    """Tests for the CDP-based cookie extraction path.

    The new implementation runs the CDP client on Windows Python via PowerShell
    (Edge binds 9222 to 127.0.0.1 which is not reachable from WSL2). Tests mock
    subprocess.run and pathlib.Path.write_text — no WSL-side websocket/requests needed.
    """

    def _make_mock_run(self, ps_output=None, ps_returncode=0):
        """Return a subprocess.run side-effect that yields ps_output / ps_returncode."""
        def side_effect(cmd, **kwargs):
            return MagicMock(returncode=ps_returncode,
                             stdout=ps_output or "", stderr="")
        return side_effect

    def test_cdp_returns_cookies_from_powershell_output(self):
        """_extract_via_cdp parses JSON from the Windows Python CDP script output."""
        cdp_output = json.dumps({"BbRouter": "tok123", "JSESSIONID": "sid456"})

        from cookie_extractor import _extract_via_cdp
        with patch("cookie_extractor.subprocess.run",
                   side_effect=self._make_mock_run(ps_output=cdp_output)), \
             patch("pathlib.Path.write_text"):
            result = _extract_via_cdp("studentcentral.brighton.ac.uk")

        self.assertEqual(result["BbRouter"], "tok123")
        self.assertEqual(result["JSESSIONID"], "sid456")

    def test_cdp_does_not_call_sudo(self):
        """_extract_via_cdp must NOT call sudo — it runs on Windows, sudo is irrelevant."""
        cdp_output = json.dumps({"BbRouter": "tok123"})

        from cookie_extractor import _extract_via_cdp
        with patch("cookie_extractor.subprocess.run",
                   side_effect=self._make_mock_run(ps_output=cdp_output)) as mock_run, \
             patch("pathlib.Path.write_text"):
            _extract_via_cdp("studentcentral.brighton.ac.uk")

        for call in mock_run.call_args_list:
            cmd = call[0][0]  # first positional arg is the command list
            self.assertNotIn("sudo", " ".join(str(c) for c in cmd),
                             "sudo must never be called from _extract_via_cdp")

    def test_cdp_raises_on_powershell_failure(self):
        """_extract_via_cdp raises RuntimeError when the PowerShell command exits non-zero."""
        from cookie_extractor import _extract_via_cdp
        with patch("cookie_extractor.subprocess.run",
                   side_effect=self._make_mock_run(ps_returncode=1)), \
             patch("pathlib.Path.write_text"):
            with self.assertRaises(RuntimeError) as ctx:
                _extract_via_cdp("studentcentral.brighton.ac.uk")
        self.assertIn("CDP extraction failed", str(ctx.exception))

    def test_cdp_raises_on_empty_output(self):
        """_extract_via_cdp raises RuntimeError when PowerShell succeeds but returns no JSON."""
        from cookie_extractor import _extract_via_cdp
        with patch("cookie_extractor.subprocess.run",
                   side_effect=self._make_mock_run(ps_output="")), \
             patch("pathlib.Path.write_text"):
            with self.assertRaises(RuntimeError) as ctx:
                _extract_via_cdp("studentcentral.brighton.ac.uk")
        self.assertIn("no output", str(ctx.exception))


    def test_cdp_kills_edge_before_launching_with_debug_port(self):
        """PS command must Stop-Process (kill) before Start-Job (launch Edge via job to bypass singleton)."""
        from cookie_extractor import _CDP_PS_CMD
        kill_pos = _CDP_PS_CMD.find("Stop-Process")
        launch_pos = _CDP_PS_CMD.find("Start-Job")
        self.assertGreater(kill_pos, -1, "PS command must contain Stop-Process")
        self.assertGreater(launch_pos, -1, "PS command must use Start-Job to launch Edge")
        self.assertLess(kill_pos, launch_pos, "Stop-Process must appear before Start-Job")

if __name__ == '__main__':
    unittest.main()
