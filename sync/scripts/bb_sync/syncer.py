import json
import re
from html.parser import HTMLParser
from pathlib import Path
from bb_client import BlackboardClient


def _safe_name(name: str) -> str:
    """Sanitise a Blackboard title for use as a folder/file name."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')


class _AttachmentLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []  # list of (file_name, resource_url)

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        raw = attrs_dict.get("data-bbfile", "")
        if not raw:
            return
        try:
            bbfile = json.loads(raw)
        except json.JSONDecodeError:
            return
        if bbfile.get("isDecorative") or bbfile.get("render") == "inlineOnly":
            return
        # fileName/displayName for data-bbtype="attachment" style; linkName for bare embed style
        file_name = bbfile.get("fileName") or bbfile.get("displayName") or bbfile.get("linkName")
        # Prefer href (stable bbcswebdav URL) over resourceUrl (may be a short-lived session URL)
        href = attrs_dict.get("href", "")
        resource_url = href if href else bbfile.get("resourceUrl", "")
        if file_name and resource_url:
            self.links.append((file_name, resource_url))


class Syncer:
    def __init__(self, client: BlackboardClient, local_root: str):
        self._client = client
        self._root = Path(local_root)

    def sync_course(self, course_id: str, course_name: str, local_folder: str):
        """Sync all content for one course into local_folder (absolute path)."""
        dest = Path(local_folder)
        dest.mkdir(parents=True, exist_ok=True)
        print(f"  Syncing course: {course_name} → {dest}")
        contents = self._client.get_contents(course_id)
        self._walk_contents(course_id, contents, dest)

    def _walk_contents(self, course_id: str, contents: list, dest: Path):
        for item in contents:
            title = _safe_name(item.get("title", "Untitled"))
            if self._client.is_folder(item):
                folder_dest = dest / title
                folder_dest.mkdir(parents=True, exist_ok=True)
                children = self._client.get_contents(course_id, item["id"])
                self._walk_contents(course_id, children, folder_dest)
            else:
                attachments = self._client.get_attachments(course_id, item["id"])
                for att in attachments:
                    self._download_attachment(course_id, item["id"], att, str(dest))
                if not attachments:
                    self._save_body(course_id, item, dest)

    def _save_body(self, course_id: str, item: dict, dest: Path):
        handler = item.get("contentHandler", {}).get("id", "")
        if handler != "resource/x-bb-document":
            return
        title = _safe_name(item.get("title", "Untitled"))
        dest_path = dest / f"{title}.html"
        body = item.get("body") or self._client.get_content_body(course_id, item["id"])
        if not body:
            return
        if not dest_path.exists():
            print(f"    [save body] {title}.html")
            dest_path.write_text(
                f"<html><head><meta charset='utf-8'><title>{title}</title></head>"
                f"<body>{body}</body></html>",
                encoding="utf-8",
            )
        else:
            print(f"    [skip] {title}.html")
        self._download_inline_attachments(body, dest)

    def _stream_to_file(self, url: str, dest_path: Path) -> None:
        tmp = dest_path.with_suffix(dest_path.suffix + ".tmp")
        try:
            with self._client.download_stream(url) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            tmp.rename(dest_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _download_inline_attachments(self, body: str, dest: Path):
        parser = _AttachmentLinkParser()
        parser.feed(body)
        for file_name, resource_url in parser.links:
            safe = _safe_name(file_name)
            dest_path = dest / safe
            if dest_path.exists():
                print(f"    [skip] {safe}")
                continue
            print(f"    [download inline] {safe}")
            self._stream_to_file(resource_url, dest_path)

    def _download_attachment(self, course_id: str, content_id: str,
                              attachment: dict, dest_dir: str):
        filename = _safe_name(attachment.get("fileName", attachment["id"]))
        dest_path = Path(dest_dir) / filename
        if dest_path.exists():
            print(f"    [skip] {filename}")
            return
        url = self._client.download_url(course_id, content_id, attachment["id"])
        print(f"    [download] {filename}")
        self._stream_to_file(url, dest_path)
