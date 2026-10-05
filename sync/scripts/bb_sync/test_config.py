# scripts/bb_sync/test_config.py
import sys
import unittest
sys.path.insert(0, '.')
from unittest.mock import patch
import config
from config import should_sync_course, current_term_codes

class TestCurrentTermCodes(unittest.TestCase):
    def test_picks_largest_term(self):
        courses = [
            {"name": "FA565 - A", "term_id": "_old"},
            {"name": "BY138 - B", "term_id": "_new"},
            {"name": "BY150 - C", "term_id": "_new"},
            {"name": "Library Skills", "term_id": "_new"},
        ]
        self.assertEqual(current_term_codes(courses), {"BY138", "BY150"})

    def test_tie_goes_to_latest_year(self):
        courses = [
            {"name": "2024 EC463 Economics", "term_id": "_164"},
            {"name": "2024 FA454 Accounting", "term_id": "_164"},
            {"name": "2026 FN678 Fintech", "term_id": "_329"},
            {"name": "2026 FN668 Risk", "term_id": "_329"},
        ]
        self.assertEqual(current_term_codes(courses), {"FN678", "FN668"})
        self.assertEqual(current_term_codes(list(reversed(courses))), {"FN678", "FN668"})

    def test_falls_back_to_all_coded(self):
        self.assertEqual(current_term_codes([{"name": "FA565 - A"}, {"name": "Misc"}]), {"FA565"})


@patch.object(config, "SYNC_MODULES", {"FA565", "FN585", "FA583"})
class TestShouldSyncCourse(unittest.TestCase):
    def test_listed_module_is_synced(self):
        self.assertTrue(should_sync_course("FN585 - Corporate Finance"))

    def test_unlisted_module_is_skipped(self):
        self.assertFalse(should_sync_course("BY150 - Introduction to Business"))

    def test_only_three_modules_are_synced(self):
        cases = [
            "FA565 - Financial Reporting",
            "FN585 - Corporate Finance",
            "FA583 - Advanced Accounting",
        ]
        for course_name in cases:
            with self.subTest(course_name=course_name):
                self.assertTrue(should_sync_course(course_name))

    def test_removed_modules_are_not_synced(self):
        cases = [
            "FN581 - Investments",
            "LW570 - Business Law",
            "MA583 - Quantitative Methods",
        ]
        for course_name in cases:
            with self.subTest(course_name=course_name):
                self.assertFalse(should_sync_course(course_name))

    def test_course_with_no_code_is_skipped(self):
        self.assertFalse(should_sync_course("General Resources"))

if __name__ == '__main__':
    unittest.main()
