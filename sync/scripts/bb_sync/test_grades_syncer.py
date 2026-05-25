import sys, json, unittest, copy
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

ASSIGNMENTS_FOR_PROMOTE = [
    {
        "id": "fa565-task-1",
        "module_code": "FA565",
        "assignment_title": "Task 1",
        "weighting_percent": 40,
        "status": "upcoming",
    }
]

class TestGradeSyncer(unittest.TestCase):
    def test_sync_writes_grades_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            mock_cdp = MagicMock()
            mock_cdp.get_all_cookies.return_value = {}
            client = BlackboardClient(mock_cdp)
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with (patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
                  patch.object(client, 'get_column_grade',
                               side_effect=[{"score": 68.0, "bb_status": "Graded"}, {"score": None, "bb_status": "Ungraded"}])):
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
            mock_cdp = MagicMock()
            mock_cdp.get_all_cookies.return_value = {}
            client = BlackboardClient(mock_cdp)
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
            mock_cdp = MagicMock()
            mock_cdp.get_all_cookies.return_value = {}
            client = BlackboardClient(mock_cdp)
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with patch.object(client, 'get_gradebook_columns', return_value=[]) as mock_cols:
                syncer.sync("_user_1")
            # Both FA565 and MA583 are in assessments, so both should be attempted
            self.assertEqual(mock_cols.call_count, 2)

    def test_sync_writes_bb_status(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            from grades import GradeSyncer
            from bb_client import BlackboardClient
            mock_cdp = MagicMock()
            mock_cdp.get_all_cookies.return_value = {}
            client = BlackboardClient(mock_cdp)
            assessments_path = tmp / "assessments.json"
            assessments_path.write_text(json.dumps(ASSESSMENTS))
            grades_path = tmp / "grades.json"
            syncer = GradeSyncer(client, assessments_path, grades_path)
            with (patch.object(client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
                  patch.object(client, 'get_column_grade',
                               side_effect=[{"score": 68.0, "bb_status": "Graded"}, {"score": None, "bb_status": "NeedsGrading"}])):
                syncer.sync("_user_1", modules=["FA565"])
            out = json.loads(grades_path.read_text())
            cols = out["FA565"]["columns"]
            self.assertEqual(cols[0]["bb_status"], "Graded")
            self.assertEqual(cols[1]["bb_status"], "NeedsGrading")

class TestPromoteStatuses(unittest.TestCase):
    def setUp(self):
        from grades import GradeSyncer
        from bb_client import BlackboardClient
        import tempfile
        self.d = tempfile.TemporaryDirectory()
        self.tmp = Path(self.d.name)
        mock_cdp = MagicMock()
        mock_cdp.get_all_cookies.return_value = {}
        self.client = BlackboardClient(mock_cdp)
        self.assessments_path = self.tmp / "assessments.json"
        self.assessments_path.write_text(json.dumps(ASSESSMENTS))
        self.grades_path = self.tmp / "grades.json"
        self.assignments_path = self.tmp / "assignments.json"

    def tearDown(self):
        self.d.cleanup()

    def test_promotes_to_submitted_on_needs_grading(self):
        from grades import GradeSyncer
        self.assignments_path.write_text(json.dumps(copy.deepcopy(ASSIGNMENTS_FOR_PROMOTE)))
        syncer = GradeSyncer(self.client, self.assessments_path, self.grades_path, self.assignments_path)
        with (patch.object(self.client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
              patch.object(self.client, 'get_column_grade',
                           side_effect=[{"score": None, "bb_status": "NeedsGrading"}, {"score": None, "bb_status": "NotAttempted"}])):
            syncer.sync("_user_1", modules=["FA565"])
        updated = json.loads(self.assignments_path.read_text())
        self.assertEqual(updated[0]["status"], "submitted")

    def test_promotes_to_graded_on_score(self):
        from grades import GradeSyncer
        self.assignments_path.write_text(json.dumps(copy.deepcopy(ASSIGNMENTS_FOR_PROMOTE)))
        syncer = GradeSyncer(self.client, self.assessments_path, self.grades_path, self.assignments_path)
        with (patch.object(self.client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
              patch.object(self.client, 'get_column_grade',
                           side_effect=[{"score": 72.0, "bb_status": "Graded"}, {"score": None, "bb_status": "NotAttempted"}])):
            syncer.sync("_user_1", modules=["FA565"])
        updated = json.loads(self.assignments_path.read_text())
        self.assertEqual(updated[0]["status"], "graded")

    def test_never_demotes_from_graded(self):
        from grades import GradeSyncer
        graded_assignment = copy.deepcopy(ASSIGNMENTS_FOR_PROMOTE)
        graded_assignment[0]["status"] = "graded"
        self.assignments_path.write_text(json.dumps(graded_assignment))
        syncer = GradeSyncer(self.client, self.assessments_path, self.grades_path, self.assignments_path)
        with (patch.object(self.client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
              patch.object(self.client, 'get_column_grade',
                           side_effect=[{"score": None, "bb_status": "NotAttempted"}, {"score": None, "bb_status": "NotAttempted"}])):
            syncer.sync("_user_1", modules=["FA565"])
        updated = json.loads(self.assignments_path.read_text())
        self.assertEqual(updated[0]["status"], "graded")

    def test_noop_when_no_assignments_path(self):
        from grades import GradeSyncer
        syncer = GradeSyncer(self.client, self.assessments_path, self.grades_path, assignments_path=None)
        with (patch.object(self.client, 'get_gradebook_columns', return_value=COLUMNS_FA565),
              patch.object(self.client, 'get_column_grade',
                           side_effect=[{"score": None, "bb_status": "NeedsGrading"}, {"score": None, "bb_status": "NotAttempted"}])):
            syncer.sync("_user_1", modules=["FA565"])
        self.assertTrue(self.grades_path.exists())
        self.assertFalse(self.assignments_path.exists())

if __name__ == '__main__':
    unittest.main()
