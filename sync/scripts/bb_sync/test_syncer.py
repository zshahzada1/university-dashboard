import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, '.')
from syncer import Syncer

class TestSyncer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()

    def test_skips_existing_file(self):
        dest = Path(self.tmpdir) / "week1.pdf"
        dest.write_bytes(b"existing")
        syncer = Syncer(self.client, self.tmpdir)
        syncer._download_attachment(
            course_id="_1_1",
            content_id="_10_1",
            attachment={"id": "_99_1", "fileName": "week1.pdf"},
            dest_dir=self.tmpdir
        )
        self.client.download_url.assert_not_called()

    def test_downloads_missing_file(self):
        dest = Path(self.tmpdir) / "new.pdf"
        self.assertFalse(dest.exists())

        fake_response = MagicMock()
        fake_response.iter_content = MagicMock(return_value=[b"data"])
        fake_response.raise_for_status = MagicMock()
        fake_response.__enter__ = MagicMock(return_value=fake_response)
        fake_response.__exit__ = MagicMock(return_value=False)

        self.client.download_url.return_value = "https://fake/download"
        self.client.download_stream.return_value = fake_response
        syncer = Syncer(self.client, self.tmpdir)
        syncer._download_attachment(
            course_id="_1_1",
            content_id="_10_1",
            attachment={"id": "_99_1", "fileName": "new.pdf"},
            dest_dir=self.tmpdir
        )
        self.assertTrue(dest.exists())

    def test_sync_course_creates_folder(self):
        """sync_course creates the local folder if it doesn't exist."""
        import os
        new_folder = os.path.join(self.tmpdir, "FN585")
        self.client.get_contents.return_value = []
        syncer = Syncer(self.client, self.tmpdir)
        syncer.sync_course("_1_1", "FN585 - Corporate Finance", new_folder)
        self.assertTrue(os.path.isdir(new_folder))

class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.client.download_url.return_value = "https://fake/download"
        self.client.is_folder.return_value = False
        self.client.get_attachments.return_value = [{"id": "_a_1", "fileName": "slides.pdf"}]

    def _resp(self, data):
        r = MagicMock()
        r.iter_content.return_value = [data]
        r.__enter__ = MagicMock(return_value=r)
        r.__exit__ = MagicMock(return_value=False)
        return r

    def _sync(self, modified):
        self.client.get_contents.return_value = [{"id": "_c_1", "title": "Week 1", "modified": modified}]
        Syncer(self.client, self.tmpdir).sync_course("_1_1", "FA565", self.tmpdir)

    def test_redownloads_when_blackboard_item_changes(self):
        self.client.download_stream.return_value = self._resp(b"v1")
        self._sync("2026-01-01T00:00:00Z")
        self.client.download_stream.return_value = self._resp(b"v2")
        self._sync("2026-01-01T00:00:00Z")   # unchanged -> skip
        self.assertEqual((Path(self.tmpdir) / "slides.pdf").read_bytes(), b"v1")
        self._sync("2026-02-01T00:00:00Z")   # lecturer re-uploaded
        self.assertEqual((Path(self.tmpdir) / "slides.pdf").read_bytes(), b"v2")

    def test_existing_file_without_manifest_is_adopted(self):
        (Path(self.tmpdir) / "slides.pdf").write_bytes(b"old")
        self._sync("2026-01-01T00:00:00Z")
        self.client.download_stream.assert_not_called()

    def test_one_failing_item_does_not_abort_course(self):
        self.client.get_contents.return_value = [
            {"id": "_c_1", "title": "Bad"}, {"id": "_c_2", "title": "Good"}]
        self.client.get_attachments.side_effect = [RuntimeError("boom"), [{"id": "_a_2", "fileName": "ok.pdf"}]]
        self.client.download_stream.return_value = self._resp(b"x")
        Syncer(self.client, self.tmpdir).sync_course("_1_1", "FA565", self.tmpdir)
        self.assertTrue((Path(self.tmpdir) / "ok.pdf").exists())


class TestDownloadInlineAttachments(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.syncer = Syncer(self.client, self.tmpdir)

    def _make_body(self, items):
        """items = list of (fileName, resourceUrl, isDecorative)"""
        import json as _json
        import html as _html
        links = ""
        for fname, url, decorative in items:
            bbfile = _json.dumps({
                "fileName": fname,
                "displayName": fname,
                "resourceUrl": url,
                "isDecorative": decorative,
            })
            links += f'<a data-bbtype="attachment" data-bbfile="{_html.escape(bbfile)}">{fname}</a>'
        return f"<div>{links}</div>"

    def _fake_resp(self, data=b"data"):
        r = MagicMock()
        r.iter_content.return_value = [data]
        r.raise_for_status = MagicMock()
        r.__enter__ = MagicMock(return_value=r)
        r.__exit__ = MagicMock(return_value=False)
        return r

    def test_downloads_inline_docx(self):
        body = self._make_body([("Brief.docx", "https://fake/Brief.docx", False)])
        self.client.download_stream.return_value = self._fake_resp(b"pdfdata")
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "Brief.docx").exists())

    def test_skips_decorative_images(self):
        body = self._make_body([("banner.png", "https://fake/banner.png", True)])
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()
        self.assertFalse((Path(self.tmpdir) / "banner.png").exists())

    def test_skips_existing_file(self):
        existing = Path(self.tmpdir) / "Brief.docx"
        existing.write_bytes(b"existing")
        body = self._make_body([("Brief.docx", "https://fake/Brief.docx", False)])
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()

    def test_no_links_does_nothing(self):
        body = "<div><p>No attachments here</p></div>"
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()

    def test_downloads_bare_embed_style(self):
        """Attachments with no data-bbtype, only linkName in data-bbfile (FA583-style)."""
        import json as _json
        import html as _html
        bbfile = _json.dumps({
            "linkName": "FA583 Exam Paper.pdf",
            "mimeType": "application/pdf",
            "alternativeText": "FA583 Exam Paper.pdf",
        })
        body = f'<a data-bbfile="{_html.escape(bbfile)}" href="https://fake/exam.pdf"></a>'
        self.client.download_stream.return_value = self._fake_resp(b"pdfdata")
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "FA583 Exam Paper.pdf").exists())


class TestPageLinkedFiles(unittest.TestCase):
    """Files a page shows inline or links to — the cases that were silently skipped."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.client.is_blackboard_url.side_effect = lambda u: "studentcentral" in u or u.startswith("/")
        self.client.is_sharepoint_url.side_effect = lambda u: ".sharepoint.com" in u
        self.syncer = Syncer(self.client, self.tmpdir)

    def _resp(self):
        r = MagicMock()
        r.iter_content.return_value = [b"pdf"]
        r.__enter__ = MagicMock(return_value=r)
        r.__exit__ = MagicMock(return_value=False)
        return r

    def test_inline_only_embed_is_downloaded(self):
        """render=inlineOnly means 'displayed in the page', not 'skip' (FN678 past papers)."""
        import json as _json, html as _html
        bbfile = _json.dumps({"linkName": "FN678 Final exam Q&As from previous years.pdf",
                              "render": "inlineOnly", "isDecorative": False})
        body = f'<a data-bbfile="{_html.escape(bbfile)}" href="https://studentcentral.brighton.ac.uk/bbcswebdav/x.pdf">x</a>'
        self.client.download_stream.return_value = self._resp()
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "FN678 Final exam Q&As from previous years.pdf").exists())

    def test_decorative_inline_only_image_still_skipped(self):
        import json as _json, html as _html
        bbfile = _json.dumps({"linkName": "banner.png", "render": "inlineOnly", "isDecorative": True})
        body = f'<a data-bbfile="{_html.escape(bbfile)}" href="/bbcswebdav/banner.png"></a>'
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()

    def test_plain_document_link_on_blackboard_is_downloaded(self):
        body = '<p><a href="/bbcswebdav/pid-1/Reading%20List.pdf">Reading List.pdf</a></p>'
        self.client.download_stream.return_value = self._resp()
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "Reading List.pdf").exists())

    def test_plain_non_document_link_is_ignored(self):
        body = '<a href="https://www.ft.com/markets">FT markets</a><a href="/ultra/course">course</a>'
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()
        self.client.download_sharepoint.assert_not_called()

    def test_sharepoint_link_downloads_via_browser_session(self):
        body = ('<a href="https://unibrightonac.sharepoint.com/:w:/r/sites/cr/moduledocs/FN668.docx'
                '?d=wabc&amp;csf=1">FN668.docx</a>')
        self.client.download_sharepoint.return_value = ("FN668.docx", b"PK")
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_sharepoint.assert_called_once_with(
            "https://unibrightonac.sharepoint.com/:w:/r/sites/cr/moduledocs/FN668.docx?d=wabc&csf=1")
        self.assertEqual((Path(self.tmpdir) / "FN668.docx").read_bytes(), b"PK")

    def test_sharepoint_moved_file_saved_under_real_name(self):
        body = '<a href="https://x.sharepoint.com/sites/cr/FN668.docx">FN668.docx</a>'
        self.client.download_sharepoint.return_value = ("FN668.pdf", b"%PDF")
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "FN668.pdf").exists())
        self.assertFalse((Path(self.tmpdir) / "FN668.docx").exists())

    def test_dead_sharepoint_link_is_reported_not_fatal(self):
        body = '<a href="https://x.sharepoint.com/sites/cr/Gone.docx">Gone.docx</a>'
        self.client.download_sharepoint.return_value = None
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertEqual(self.syncer._errors, 1)
        self.assertEqual(list(Path(self.tmpdir).iterdir()), [])

    def test_document_on_other_website_is_not_downloaded(self):
        body = '<a href="https://publisher.example.com/chapter1.pdf">chapter1.pdf</a>'
        self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.client.download_stream.assert_not_called()
        self.client.download_sharepoint.assert_not_called()


class TestSaveBodyInlineAttachments(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.syncer = Syncer(self.client, self.tmpdir)

    def test_processes_inline_attachments_even_when_html_exists(self):
        """HTML file exists from prior run — inline DOCX must still be downloaded."""
        import json as _json
        import html as _html
        bbfile = _json.dumps({"fileName": "Brief.docx", "resourceUrl": "https://fake/Brief.docx", "isDecorative": False})
        body_html = f'<a data-bbtype="attachment" data-bbfile="{_html.escape(bbfile)}">Brief.docx</a>'
        html_path = Path(self.tmpdir) / "ultraDocumentBody.html"
        html_path.write_text(body_html, encoding="utf-8")

        item = {
            "title": "ultraDocumentBody",
            "contentHandler": {"id": "resource/x-bb-document"},
            "body": body_html,
        }

        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b"docxdata"]
        fake_resp.raise_for_status = MagicMock()
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)
        self.client.download_stream.return_value = fake_resp
        self.syncer._save_body("_1_1", item, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "Brief.docx").exists())


if __name__ == '__main__':
    unittest.main()
