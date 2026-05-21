import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")
import browser_launcher as bl


class TestCdpReachable(unittest.TestCase):
    def test_true_when_port_responds(self):
        with patch("browser_launcher.urllib.request.urlopen"):
            self.assertTrue(bl.cdp_reachable())

    def test_false_when_all_ports_fail(self):
        with patch("browser_launcher.urllib.request.urlopen", side_effect=OSError):
            self.assertFalse(bl.cdp_reachable())


class TestIsWsl(unittest.TestCase):
    def test_true_when_proc_version_contains_microsoft(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.return_value = "Linux version ... microsoft-standard-WSL2"
            self.assertTrue(bl._is_wsl())

    def test_false_when_proc_version_missing(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.side_effect = FileNotFoundError
            self.assertFalse(bl._is_wsl())

    def test_false_on_plain_linux(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.return_value = "Linux version 6.1.0-generic #1 SMP"
            self.assertFalse(bl._is_wsl())


class TestFindBrowsers(unittest.TestCase):
    def test_mac_finds_chrome_when_installed(self):
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        with patch("browser_launcher.platform.system", return_value="Darwin"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: str(p) == chrome)
            browsers = bl.find_browsers()
        self.assertIn("Google Chrome", [b[0] for b in browsers])

    def test_mac_empty_when_nothing_installed(self):
        with patch("browser_launcher.platform.system", return_value="Darwin"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: False)
            self.assertEqual(bl.find_browsers(), [])

    def test_wsl_finds_edge(self):
        edge_path = "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
        with patch("browser_launcher.platform.system", return_value="Linux"), \
             patch("browser_launcher._is_wsl", return_value=True), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: str(p) == edge_path)
            browsers = bl.find_browsers()
        self.assertTrue(any(b[0] == "Microsoft Edge" for b in browsers))

    def test_linux_uses_which(self):
        with patch("browser_launcher.platform.system", return_value="Linux"), \
             patch("browser_launcher._is_wsl", return_value=False), \
             patch("browser_launcher.shutil.which",
                   side_effect=lambda cmd: "/usr/bin/google-chrome" if cmd == "google-chrome" else None):
            browsers = bl.find_browsers()
        self.assertTrue(any(b[0] == "Google Chrome" for b in browsers))

    def test_no_duplicates_when_multiple_paths_match(self):
        with patch("browser_launcher.platform.system", return_value="Windows"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: True)
            browsers = bl.find_browsers()
        names = [b[0] for b in browsers]
        self.assertEqual(len(names), len(set(names)), "Duplicate browser names found")


class TestRunWizard(unittest.TestCase):
    def test_exits_when_no_browsers_found(self):
        with patch("browser_launcher.find_browsers", return_value=[]), \
             self.assertRaises(SystemExit) as cm:
            bl.run_wizard()
        self.assertEqual(cm.exception.code, 1)

    def test_launches_selected_browser_and_waits(self):
        browsers = [("Google Chrome", "/usr/bin/google-chrome")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser") as mock_launch, \
             patch("browser_launcher._wait_for_cdp", return_value=True), \
             patch("builtins.input", side_effect=["1", ""]):
            bl.run_wizard()
        mock_launch.assert_called_once_with("/usr/bin/google-chrome")

    def test_defaults_to_first_browser_on_empty_input(self):
        browsers = [("Chrome", "/a"), ("Edge", "/b")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser") as mock_launch, \
             patch("browser_launcher._wait_for_cdp", return_value=True), \
             patch("builtins.input", side_effect=["", ""]):
            bl.run_wizard()
        mock_launch.assert_called_once_with("/a")

    def test_exits_when_browser_never_opens_port(self):
        browsers = [("Chrome", "/a")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser"), \
             patch("browser_launcher._wait_for_cdp", return_value=False), \
             patch("builtins.input", return_value="1"), \
             self.assertRaises(SystemExit) as cm:
            bl.run_wizard()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
