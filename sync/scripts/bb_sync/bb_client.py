import requests
from config import BB_BASE_URL

FOLDER_TYPES = {
    "resource/x-bb-folder",
    "resource/x-bb-coursetoc",
    "resource/x-bb-lesson",
}

class BlackboardClient:
    def __init__(self, cdp):
        self._cdp = cdp
        self._base = BB_BASE_URL.rstrip("/")
        self._session = requests.Session()
        self._session.cookies.update(cdp.get_all_cookies())

    def _get(self, path: str, params: dict = None) -> dict:
        return self._cdp.fetch_json(path, params)

    def download_stream(self, url: str):
        return self._session.get(url, stream=True, allow_redirects=True, timeout=60)

    def get_current_user(self) -> dict:
        return self._get("/learn/api/public/v1/users/me")

    def get_courses(self, user_id: str) -> list:
        data = self._get(
            f"/learn/api/public/v1/users/{user_id}/courses",
            params={"limit": 200, "expand": "course"}
        )
        results = []
        for enrollment in data.get("results", []):
            avail = (enrollment.get("availability") or {}).get("available")
            if avail != "Yes":
                continue
            course = enrollment.get("course", {})
            results.append({
                "id": course.get("id") or enrollment.get("courseId", ""),
                "name": course.get("name", ""),
                "courseId": course.get("courseId", ""),
                "term_id": course.get("termId") or enrollment.get("termId") or "",
            })
        return results

    def get_contents(self, course_id: str, parent_id: str = None) -> list:
        if parent_id:
            path = f"/learn/api/public/v1/courses/{course_id}/contents/{parent_id}/children"
        else:
            path = f"/learn/api/public/v1/courses/{course_id}/contents"

        params = {"limit": 200}
        all_results = []
        while path:
            data = self._get(path, params=params)
            all_results.extend(data.get("results", []))
            path = (data.get("paging") or {}).get("nextPage")
            params = {}  # nextPage URL already contains all query params
        return all_results

    def get_attachments(self, course_id: str, content_id: str) -> list:
        try:
            data = self._get(
                f"/learn/api/public/v1/courses/{course_id}/contents/{content_id}/attachments"
            )
            return data.get("results", [])
        except requests.HTTPError as e:
            if e.response.status_code in (400, 403, 404):
                return []  # content item has no attachments (link, quiz, etc.)
            raise

    def get_gradebook_columns(self, course_id: str) -> list | None:
        """Returns list of {id, name, possible} or None on 403/404."""
        try:
            data = self._get(f"/learn/api/public/v2/courses/{course_id}/gradebook/columns",
                             params={"limit": 200})
            return [
                {
                    "id": col["id"],
                    "name": col.get("name", ""),
                    "possible": (col.get("score") or {}).get("possible"),
                }
                for col in data.get("results", [])
            ]
        except requests.HTTPError as e:
            if e.response.status_code in (403, 404):
                return None
            raise

    def get_column_grade(self, course_id: str, column_id: str, user_id: str) -> dict:
        """Returns {score: float|None, bb_status: str|None}."""
        try:
            data = self._get(
                f"/learn/api/public/v2/courses/{course_id}"
                f"/gradebook/columns/{column_id}/users/{user_id}"
            )
            score = data.get("score") or (data.get("displayGrade") or {}).get("score")
            return {"score": score, "bb_status": data.get("status")}
        except requests.HTTPError as e:
            if e.response.status_code in (403, 404):
                return {"score": None, "bb_status": None}
            raise

    def get_content_body(self, course_id: str, content_id: str) -> str:
        try:
            data = self._get(f"/learn/api/public/v1/courses/{course_id}/contents/{content_id}")
            return data.get("body", "")
        except requests.HTTPError:
            return ""

    def download_url(self, course_id: str, content_id: str, attachment_id: str) -> str:
        return (
            f"{self._base}/learn/api/public/v1/courses/{course_id}"
            f"/contents/{content_id}/attachments/{attachment_id}/download"
        )

    def is_folder(self, content_item: dict) -> bool:
        handler = content_item.get("contentHandler", {}).get("id", "")
        return handler in FOLDER_TYPES
