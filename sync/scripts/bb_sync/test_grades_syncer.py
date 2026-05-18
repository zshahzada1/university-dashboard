import sys, json, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, '.')

ASSESSMENTS = {
    "FA565": {
        "name": "Business Ethics",
        "course_id": "_130565_1",
        "credits": 20,
        "assessments": [
            {"title": "Task 1", "weight_percent": 40, "column_name": "Task 1"},
            {"title": "Task 2", "weight_percent": 60, "column_name": "Task 2"},
        ]
    },
    "MA583": {
        "name": "MA583",
        "course_id": "_999_1",
        "credits": 20,
        "assessments": [{"title": "Exam", "weight_percent": 100, "column_name": "Exam"}]
    }
}

COLUMNS_FA565 = [
    {"id": "_col1_1", "name": "Task 1", "possible": 100.0},
    {"id": "_col2_1", "name": "Task 2", "possible": 100.0},
]

class TestGradeSyncer(unittest.TestCase):
    def test_sync_writes_grades_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            client = BlackboardClient({"BbRouter": "fake"})
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565), \
                 patch.object(client, 'get_column_grade',
                              side_effect=[{"score": 68.0}, {"score": None}]):
                syncer.sync("_user_1", modules=["FA565"])
            out = json.loads(grades_path.read_text())
            self.assertIn("synced_at", out)
            cols = out["FA565"]["columns"]
            self.assertEqual(len(cols), 2)
            self.assertEqual(cols[0]["name"], "Task 1")
            self.assertEqual(cols[0]["score"], 68.0)
            self.assertEqual(cols[0]["status"], "graded")
            self.assertIsNone(cols[1]["score"])
            self.assertEqual(cols[1]["status"], "ungraded")

    def test_sync_403_records_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            client = BlackboardClient({"BbRouter": "fake"})
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with patch.object(client, 'get_gradebook_columns', return_value=None):
                syncer.sync("_user_1", modules=["MA583"])
            out = json.loads(grades_path.read_text())
            self.assertEqual(out["MA583"]["error"], "no gradebook access")

    def test_sync_all_modules_by_default(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            client = BlackboardClient({"BbRouter": "fake"})
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with patch.object(client, 'get_gradebook_columns', return_value=[]) as mock_cols:
                syncer.sync("_user_1")
            # Both FA565 and MA583 are in assessments, so both should be attempted
            self.assertEqual(mock_cols.call_count, 2)

if __name__ == '__main__':
    unittest.main()
