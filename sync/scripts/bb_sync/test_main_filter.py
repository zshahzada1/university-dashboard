# scripts/bb_sync/test_main_filter.py
import sys
import importlib
import unittest
from unittest.mock import MagicMock, patch
import io
import json
import pathlib
import importlib.util

sys.path.insert(0, '.')


class TestMainFilter(unittest.TestCase):
    def setUp(self):
        sys.modules.pop('bb_sync_main', None)

    def tearDown(self):
        sys.modules.pop('bb_sync_main', None)

    def test_unlisted_course_is_not_synced(self):
        """Courses outside SYNC_MODULES must not be passed to syncer.sync_course."""
        mock_client = MagicMock()
        mock_client.get_current_user.return_value = {"id": "u1", "userName": "testuser"}
        mock_client.get_courses.return_value = [
            {"id": "_1_1", "name": "BY150 - Introduction to Business"},
            {"id": "_2_1", "name": "FN585 - Corporate Finance"},
        ]
        mock_syncer = MagicMock()

        main_mod = self._load_main_module()

        with patch('bb_sync_main.CdpSession'), \
             patch('bb_sync_main.BlackboardClient', return_value=mock_client), \
             patch('bb_sync_main.Syncer', return_value=mock_syncer), \
             patch('sys.argv', ['bb_sync']):
            main_mod.main()

        synced_names = [
            call.args[1] for call in mock_syncer.sync_course.call_args_list
        ]
        self.assertNotIn("BY150 - Introduction to Business", synced_names)
        self.assertIn("FN585 - Corporate Finance", synced_names)


    def _load_main_module(self):
        """Load __main__.py fresh so patches bind into its namespace."""
        sys.modules.pop('bb_sync_main', None)
        spec = importlib.util.spec_from_file_location(
            'bb_sync_main',
            pathlib.Path(__file__).parent / '__main__.py'
        )
        main_mod = importlib.util.module_from_spec(spec)
        sys.modules['bb_sync_main'] = main_mod
        spec.loader.exec_module(main_mod)
        return main_mod

    def test_modules_flag_syncs_only_selected(self):
        """--modules FA565 syncs only FA565 even when FN585 is available."""
        mock_client = MagicMock()
        mock_client.get_current_user.return_value = {"id": "u1", "userName": "testuser"}
        mock_client.get_courses.return_value = [
            {"id": "_1_1", "name": "FA565 - Financial Reporting"},
            {"id": "_2_1", "name": "FN585 - Corporate Finance"},
        ]
        mock_syncer = MagicMock()
        main_mod = self._load_main_module()

        with patch('bb_sync_main.CdpSession'), \
             patch('bb_sync_main.BlackboardClient', return_value=mock_client), \
             patch('bb_sync_main.Syncer', return_value=mock_syncer), \
             patch('sys.argv', ['bb_sync', '--modules', 'FA565']):
            main_mod.main()

        synced = [call.args[1] for call in mock_syncer.sync_course.call_args_list]
        self.assertIn("FA565 - Financial Reporting", synced)
        self.assertNotIn("FN585 - Corporate Finance", synced)

    def test_modules_flag_accepts_multiple_codes(self):
        """--modules FA565 FN585 syncs both specified modules but not BY150."""
        mock_client = MagicMock()
        mock_client.get_current_user.return_value = {"id": "u1", "userName": "testuser"}
        mock_client.get_courses.return_value = [
            {"id": "_1_1", "name": "FA565 - Financial Reporting"},
            {"id": "_2_1", "name": "FN585 - Corporate Finance"},
            {"id": "_3_1", "name": "BY150 - Introduction to Business"},
        ]
        mock_syncer = MagicMock()
        main_mod = self._load_main_module()

        with patch('bb_sync_main.CdpSession'), \
             patch('bb_sync_main.BlackboardClient', return_value=mock_client), \
             patch('bb_sync_main.Syncer', return_value=mock_syncer), \
             patch('sys.argv', ['bb_sync', '--modules', 'FA565', 'FN585']):
            main_mod.main()

        synced = [call.args[1] for call in mock_syncer.sync_course.call_args_list]
        self.assertIn("FA565 - Financial Reporting", synced)
        self.assertIn("FN585 - Corporate Finance", synced)
        self.assertNotIn("BY150 - Introduction to Business", synced)

    def test_list_courses_outputs_all_as_json(self):
        """--list-courses prints JSON of ALL courses (not filtered) to stdout and exits 0."""
        mock_client = MagicMock()
        mock_client.get_current_user.return_value = {"id": "u1", "userName": "testuser"}
        mock_client.get_courses.return_value = [
            {"id": "_1_1", "name": "FA565 - Financial Reporting"},
            {"id": "_2_1", "name": "BY150 - Introduction to Business"},
        ]
        main_mod = self._load_main_module()

        buf = io.StringIO()
        with patch('bb_sync_main.CdpSession'), \
             patch('bb_sync_main.BlackboardClient', return_value=mock_client), \
             patch('bb_sync_main.Syncer', return_value=MagicMock()), \
             patch('sys.argv', ['bb_sync', '--list-courses']), \
             patch('sys.stdout', buf):
            with self.assertRaises(SystemExit) as ctx:
                main_mod.main()

        self.assertEqual(ctx.exception.code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data), 2)
        codes = [item["code"] for item in data]
        self.assertIn("FA565", codes)
        self.assertIn("BY150", codes)
        names = [item["name"] for item in data]
        self.assertIn("FA565 - Financial Reporting", names)
        self.assertIn("BY150 - Introduction to Business", names)


if __name__ == '__main__':
    unittest.main()
