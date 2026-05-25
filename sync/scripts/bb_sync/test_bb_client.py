import sys
import unittest
from unittest.mock import patch, MagicMock
import requests
sys.path.insert(0, '.')
from bb_client import BlackboardClient

MOCK_ME = {"id": "_123_1", "userName": "student1"}
MOCK_COURSES = {"results": [
    {"courseId": "FN585", "availability": {"available": "Yes"},
     "course": {"id": "_1_1", "courseId": "FN585", "name": "FN585 - Corporate Finance"}},
    {"courseId": "FA565", "availability": {"available": "Yes"},
     "course": {"id": "_2_1", "courseId": "FA565", "name": "FA565 - Financial Accounting"}},
]}
MOCK_CONTENTS = {"results": [
    {"id": "_10_1", "title": "Week 1 Slides", "contentHandler": {"id": "resource/x-bb-folder"}},
    {"id": "_11_1", "title": "Assignment Brief", "contentHandler": {"id": "resource/x-bb-document"}},
]}
MOCK_ATTACHMENTS = {"results": [
    {"id": "_99_1", "fileName": "week1.pdf", "mimeType": "application/pdf"}
]}

class TestBlackboardClientWithCdp(unittest.TestCase):
    def _make_cdp(self, fetch_return=None, cookies=None):
        cdp = MagicMock()
        cdp.fetch_json.return_value = fetch_return or {}
        cdp.get_all_cookies.return_value = cookies or {"BbRouter": "fake"}
        return cdp

    def test_constructor_seeds_session_from_cdp_cookies(self):
        cdp = self._make_cdp(cookies={"BbRouter": "abc123"})
        client = BlackboardClient(cdp)
        self.assertEqual(client._session.cookies.get("BbRouter"), "abc123")

    def test_get_delegates_to_fetch_json(self):
        cdp = self._make_cdp(fetch_return={"id": "u1"})
        client = BlackboardClient(cdp)
        result = client._get("/learn/api/public/v1/users/me")
        cdp.fetch_json.assert_called_once_with("/learn/api/public/v1/users/me", None)
        self.assertEqual(result["id"], "u1")

    def test_get_passes_params_to_fetch_json(self):
        cdp = self._make_cdp(fetch_return={"results": []})
        client = BlackboardClient(cdp)
        client._get("/learn/api/public/v1/courses", {"limit": 200})
        cdp.fetch_json.assert_called_once_with("/learn/api/public/v1/courses", {"limit": 200})


class TestBlackboardClient(unittest.TestCase):
    def _make_client(self):
        cdp = MagicMock()
        cdp.get_all_cookies.return_value = {"BbRouter": "fake", "JSESSIONID": "fake"}
        return BlackboardClient(cdp)

    def _mock_resp(self, data):
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_get_current_user(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_ME
        user = client.get_current_user()
        self.assertEqual(user["id"], "_123_1")

    def test_get_courses(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_COURSES
        courses = client.get_courses("_123_1")
        self.assertEqual(len(courses), 2)
        self.assertEqual(courses[0]["courseId"], "FN585")

    def test_get_contents(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_CONTENTS
        contents = client.get_contents("_1_1")
        self.assertEqual(len(contents), 2)

    def test_get_attachments(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_ATTACHMENTS
        attachments = client.get_attachments("_1_1", "_10_1")
        self.assertEqual(attachments[0]["fileName"], "week1.pdf")

    def test_is_folder(self):
        client = self._make_client()
        folder_item = {"contentHandler": {"id": "resource/x-bb-folder"}}
        doc_item = {"contentHandler": {"id": "resource/x-bb-document"}}
        self.assertTrue(client.is_folder(folder_item))
        self.assertFalse(client.is_folder(doc_item))

    def test_download_url_format(self):
        client = self._make_client()
        url = client.download_url("_1_1", "_10_1", "_99_1")
        self.assertIn("studentcentral.brighton.ac.uk", url)
        self.assertIn("_1_1", url)
        self.assertIn("_99_1", url)

    def test_get_courses_filters_null_availability(self):
        """Should not crash if availability key is explicitly null."""
        mock_data = {"results": [
            {"courseId": "FN585", "availability": None,
             "course": {"id": "_1_1", "courseId": "FN585", "name": "FN585"}},
            {"courseId": "FA565", "availability": {"available": "Yes"},
             "course": {"id": "_2_1", "courseId": "FA565", "name": "FA565"}},
        ]}
        client = self._make_client()
        client._cdp.fetch_json.return_value = mock_data
        courses = client.get_courses("_123_1")
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["courseId"], "FA565")

    def test_get_contents_follows_next_page(self):
        """get_contents must return items from all pages, not just the first."""
        client = self._make_client()

        page1 = {
            "results": [{"id": "_1_1", "title": "Week 1"}],
            "paging": {"nextPage": "/learn/api/public/v1/courses/_c_1/contents?offset=1&limit=1"},
        }
        page2 = {
            "results": [{"id": "_2_1", "title": "Week 2"}],
        }

        with patch.object(client, '_get', side_effect=[page1, page2]) as mock_get:
            results = client.get_contents("_c_1")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Week 1")
        self.assertEqual(results[1]["title"], "Week 2")
        second_call_path = mock_get.call_args_list[1][0][0]
        self.assertIn("offset=1", second_call_path)

    def test_get_contents_single_page_unchanged(self):
        """get_contents with no paging key returns results normally."""
        client = self._make_client()
        single_page = {"results": [{"id": "_1_1", "title": "Week 1"}]}

        with patch.object(client, '_get', return_value=single_page):
            results = client.get_contents("_c_1")

        self.assertEqual(results, [{"id": "_1_1", "title": "Week 1"}])

MOCK_COLUMNS = {"results": [
    {"id": "_col1_1", "name": "Task 1", "score": {"possible": 100.0}},
    {"id": "_col2_1", "name": "Task 2", "score": {"possible": 100.0}},
]}
MOCK_GRADE = {"score": 68.0, "status": "Graded"}

class TestBlackboardClientGradebook(unittest.TestCase):
    def _make_client(self):
        cdp = MagicMock()
        cdp.get_all_cookies.return_value = {"BbRouter": "fake", "JSESSIONID": "fake"}
        return BlackboardClient(cdp)

    def test_get_gradebook_columns_success(self):
        client = self._make_client()
        with patch.object(client, '_get', return_value=MOCK_COLUMNS):
            cols = client.get_gradebook_columns("_130565_1")
        self.assertEqual(len(cols), 2)
        self.assertEqual(cols[0]["id"], "_col1_1")
        self.assertEqual(cols[0]["name"], "Task 1")
        self.assertEqual(cols[0]["possible"], 100.0)

    def test_get_gradebook_columns_403_returns_none(self):
        client = self._make_client()
        err = requests.HTTPError(response=MagicMock(status_code=403))
        with patch.object(client, '_get', side_effect=err):
            result = client.get_gradebook_columns("_130565_1")
        self.assertIsNone(result)

    def test_get_column_grade_returns_score(self):
        client = self._make_client()
        with patch.object(client, '_get', return_value=MOCK_GRADE):
            grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
        self.assertEqual(grade["score"], 68.0)

    def test_get_column_grade_returns_bb_status(self):
        client = self._make_client()
        mock_response = {"score": 68.0, "status": "Graded"}
        with patch.object(client, '_get', return_value=mock_response):
            grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
        self.assertEqual(grade["bb_status"], "Graded")

    def test_get_column_grade_needs_grading_status(self):
        client = self._make_client()
        with patch.object(client, '_get', return_value={"status": "NeedsGrading"}):
            grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
        self.assertIsNone(grade["score"])
        self.assertEqual(grade["bb_status"], "NeedsGrading")

    def test_get_column_grade_403_returns_none_bb_status(self):
        client = self._make_client()
        err = requests.HTTPError(response=MagicMock(status_code=403))
        with patch.object(client, '_get', side_effect=err):
            grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
        self.assertIsNone(grade["bb_status"])

    def test_get_column_grade_ungraded_returns_none_score(self):
        client = self._make_client()
        with patch.object(client, '_get', return_value={"status": "NotAttempted"}):
            grade = client.get_column_grade("_130565_1", "_col1_1", "_user_1")
        self.assertIsNone(grade["score"])

if __name__ == '__main__':
    unittest.main()
