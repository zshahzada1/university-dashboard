# ~/University/scripts/bb_sync/test_syncer.py
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
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
        self.client._cookies = {}
        syncer = Syncer(self.client, self.tmpdir)

        with patch('syncer.requests.Session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_session.return_value)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.return_value.get.return_value = fake_response
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

class TestDownloadInlineAttachments(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.client._cookies = {}
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

    def test_downloads_inline_docx(self):
        body = self._make_body([("Brief.docx", "https://fake/Brief.docx", False)])
        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b"pdfdata"]
        fake_resp.raise_for_status = MagicMock()
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch("syncer.requests.Session") as mock_sess:
            mock_sess.return_value.__enter__ = MagicMock(return_value=mock_sess.return_value)
            mock_sess.return_value.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value.get.return_value = fake_resp
            self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "Brief.docx").exists())

    def test_skips_decorative_images(self):
        body = self._make_body([("banner.png", "https://fake/banner.png", True)])
        with patch("syncer.requests.Session") as mock_sess:
            self.syncer._download_inline_attachments(body, Path(self.tmpdir))
            mock_sess.assert_not_called()
        self.assertFalse((Path(self.tmpdir) / "banner.png").exists())

    def test_skips_existing_file(self):
        existing = Path(self.tmpdir) / "Brief.docx"
        existing.write_bytes(b"existing")
        body = self._make_body([("Brief.docx", "https://fake/Brief.docx", False)])
        with patch("syncer.requests.Session") as mock_sess:
            self.syncer._download_inline_attachments(body, Path(self.tmpdir))
            mock_sess.assert_not_called()

    def test_no_links_does_nothing(self):
        body = "<div><p>No attachments here</p></div>"
        with patch("syncer.requests.Session") as mock_sess:
            self.syncer._download_inline_attachments(body, Path(self.tmpdir))
            mock_sess.assert_not_called()

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
        fake_resp = MagicMock()
        fake_resp.iter_content.return_value = [b"pdfdata"]
        fake_resp.raise_for_status = MagicMock()
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch("syncer.requests.Session") as mock_sess:
            mock_sess.return_value.__enter__ = MagicMock(return_value=mock_sess.return_value)
            mock_sess.return_value.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value.get.return_value = fake_resp
            self.syncer._download_inline_attachments(body, Path(self.tmpdir))
        self.assertTrue((Path(self.tmpdir) / "FA583 Exam Paper.pdf").exists())


class TestSaveBodyInlineAttachments(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = MagicMock()
        self.client._cookies = {}
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

        with patch("syncer.requests.Session") as mock_sess:
            mock_sess.return_value.__enter__ = MagicMock(return_value=mock_sess.return_value)
            mock_sess.return_value.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value.get.return_value = fake_resp
            self.syncer._save_body("_1_1", item, Path(self.tmpdir))

        self.assertTrue((Path(self.tmpdir) / "Brief.docx").exists())


if __name__ == '__main__':
    unittest.main()
