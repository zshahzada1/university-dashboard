# scripts/bb_sync/test_config.py
import sys
import unittest
sys.path.insert(0, '.')
from config import should_sync_course

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
