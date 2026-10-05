import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from bb_client import BlackboardClient


def _safe_name(name: str, max_len: int = 180) -> str:
    """Sanitise a Blackboard title for use as a folder/file name.

    Blackboard titles can run to a full sentence, which blows past NTFS's
    255-char-per-component limit even with an extended-length path prefix.
    """
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')
    if len(cleaned) <= max_len:
        return cleaned
    root, ext = os.path.splitext(cleaned)
    if ext and len(ext) <= 10:
        return root[:max_len - len(ext)].rstrip() + ext
    return cleaned[:max_len].rstrip()


def _winpath(path: Path) -> str:
    """Extended-length path string to bypass Windows' 260-char MAX_PATH limit."""
    if sys.platform != "win32":
        return str(path)
    s = os.path.abspath(str(path))
    return s if s.startswith("\\\\?\\") else "\\\\?\\" + s


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


MANIFEST_NAME = ".bbsync-manifest.json"


class Syncer:
    """Walks a course's content tree and mirrors it locally.

    A per-course manifest records each item's Blackboard ``modified`` stamp, so a
    file the lecturer replaces is downloaded again instead of being skipped forever.
    """

    def __init__(self, client: BlackboardClient, local_root: str):
        self._client = client
        self._root = Path(local_root)
        self._manifest: dict[str, str] = {}
        self._errors = 0

    def sync_course(self, course_id: str, course_name: str, local_folder: str):
        """Sync all content for one course into local_folder (absolute path)."""
        dest = Path(local_folder)
        os.makedirs(_winpath(dest), exist_ok=True)
        print(f"  Syncing course: {course_name} → {dest}")
        manifest_path = dest / MANIFEST_NAME
        self._manifest = self._load_manifest(manifest_path)
        self._errors = 0
        try:
            contents = self._client.get_contents(course_id)
            self._walk_contents(course_id, contents, dest)
        finally:
            self._save_manifest(manifest_path)
        if self._errors:
            print(f"  [warn] {self._errors} item(s) failed in {course_name}")

    @staticmethod
    def _load_manifest(path: Path) -> dict:
        try:
            return json.loads(Path(_winpath(path)).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_manifest(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        with open(_winpath(tmp), "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=1, sort_keys=True)
        os.replace(_winpath(tmp), _winpath(path))

    def _is_current(self, key: str, dest_path: Path, modified: str | None) -> bool:
        """True if dest_path exists and Blackboard hasn't changed the item since we fetched it."""
        if not os.path.exists(_winpath(dest_path)):
            return False
        if not modified:
            return True
        recorded = self._manifest.get(key)
        if recorded is None:
            # File predates the manifest: adopt it rather than re-downloading everything.
            self._manifest[key] = modified
            return True
        return recorded == modified

    def _walk_contents(self, course_id: str, contents: list, dest: Path):
        for item in contents:
            title = _safe_name(item.get("title") or "Untitled") or "Untitled"
            try:
                if self._client.is_folder(item):
                    folder_dest = dest / title
                    os.makedirs(_winpath(folder_dest), exist_ok=True)
                    children = self._client.get_contents(course_id, item["id"])
                    self._walk_contents(course_id, children, folder_dest)
                else:
                    attachments = self._client.get_attachments(course_id, item["id"])
                    for att in attachments:
                        self._download_attachment(course_id, item["id"], att, str(dest),
                                                  modified=item.get("modified"))
                    if not attachments:
                        self._save_body(course_id, item, dest)
            except Exception as e:  # one bad item (or a file open in Word) mustn't abort the course
                self._errors += 1
                print(f"    [error] {title}: {e}")

    def _save_body(self, course_id: str, item: dict, dest: Path):
        handler = item.get("contentHandler", {}).get("id", "")
        if handler != "resource/x-bb-document":
            return
        title = _safe_name(item.get("title") or "Untitled") or "Untitled"
        dest_path = dest / f"{title}.html"
        body = item.get("body") or self._client.get_content_body(course_id, item["id"])
        if not body:
            return
        key = f"body:{item.get('id', title)}"
        modified = item.get("modified")
        if self._is_current(key, dest_path, modified):
            print(f"    [skip] {title}.html")
        else:
            print(f"    [save body] {title}.html")
            with open(_winpath(dest_path), "w", encoding="utf-8") as f:
                f.write(
                    f"<html><head><meta charset='utf-8'><title>{html.escape(title)}</title></head>"
                    f"<body>{body}</body></html>"
                )
            if modified:
                self._manifest[key] = modified
        self._download_inline_attachments(body, dest)

    def _stream_to_file(self, url: str, dest_path: Path) -> None:
        tmp = dest_path.with_suffix(dest_path.suffix + ".tmp")
        tmp_p = _winpath(tmp)
        try:
            with self._client.download_stream(url) as resp:
                resp.raise_for_status()
                with open(tmp_p, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            os.replace(tmp_p, _winpath(dest_path))
        except Exception:
            try:
                os.remove(tmp_p)
            except FileNotFoundError:
                pass
            raise

    def _download_inline_attachments(self, body: str, dest: Path):
        parser = _AttachmentLinkParser()
        parser.feed(body)
        for file_name, resource_url in parser.links:
            safe = _safe_name(file_name)
            if not safe:
                continue
            dest_path = dest / safe
            if os.path.exists(_winpath(dest_path)):
                print(f"    [skip] {safe}")
                continue
            print(f"    [download inline] {safe}")
            try:
                self._stream_to_file(resource_url, dest_path)
            except Exception as e:
                self._errors += 1
                print(f"    [error] {safe}: {e}")

    def _download_attachment(self, course_id: str, content_id: str,
                              attachment: dict, dest_dir: str, modified: str | None = None):
        filename = _safe_name(attachment.get("fileName") or attachment["id"]) or attachment["id"]
        dest_path = Path(dest_dir) / filename
        key = f"att:{content_id}/{attachment['id']}"
        if self._is_current(key, dest_path, modified):
            print(f"    [skip] {filename}")
            return
        url = self._client.download_url(course_id, content_id, attachment["id"])
        updating = os.path.exists(_winpath(dest_path))
        print(f"    [{'update' if updating else 'download'}] {filename}")
        self._stream_to_file(url, dest_path)
        if modified:
            self._manifest[key] = modified
