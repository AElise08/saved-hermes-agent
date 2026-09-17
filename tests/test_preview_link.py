#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import preview_link  # noqa: E402
from notion_ideas import capture, setup_local  # noqa: E402


IG_HTML = """
<html><head>
<meta property="og:site_name" content="Instagram" />
<meta property="og:url" content="https://www.instagram.com/productplaybook_/reel/DczJ7vtSvbp/" />
<meta name="twitter:title" content="sophia AI product manager (@productplaybook_) • Instagram reel" />
<meta name="description" content="1,729 likes, 629 comments - productplaybook_ on September 2, 2026: &quot;Last chance! If you are a student interested in content creation.&quot;" />
<meta property="og:description" content="1,729 likes, 629 comments - productplaybook_ on September 2, 2026: &quot;Last chance! If you are a student interested in content creation.&quot;" />
<meta property="og:image" content="https://example.com/poster.jpg" />
</head></html>
"""


class ParseTests(unittest.TestCase):
    def test_instagram_caption_and_author(self):
        meta = preview_link.parse_meta(IG_HTML)
        title, caption, author = preview_link.split_instagram(meta)
        self.assertEqual(author, "productplaybook_")
        self.assertIn("Last chance", caption)
        self.assertIn("productplaybook_", title)

    def test_canonical_strips_tracking(self):
        url = "https://www.instagram.com/reel/Abc/?utm_source=ig_web&igsh=xyz"
        self.assertEqual(
            preview_link.canonical_url(url),
            "https://www.instagram.com/reel/Abc/",
        )


class PreviewTests(unittest.TestCase):
    def test_preview_uses_crawler_html(self):
        with patch.object(preview_link, "fetch", return_value=(200, IG_HTML)):
            with patch.object(preview_link, "oembed", return_value={}):
                data = preview_link.preview("https://www.instagram.com/reel/Abc/")
        self.assertTrue(data["ok"])
        self.assertEqual(data["evidence"], "caption")
        self.assertEqual(data["author"], "productplaybook_")
        self.assertIn("Last chance", data["caption"])
        self.assertEqual(data["media_type"], "Vídeo")
        content = preview_link.format_content(data)
        self.assertIn("Caption (public metadata)", content)
        self.assertIn("video not watched", content)


class CaptureFromUrlTests(unittest.TestCase):
    def test_from_url_fills_title_and_caption(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HERMES_HOME": tmp}, clear=False):
                os.environ.pop("NOTION_API_KEY", None)
                setup_local()
                with patch.object(preview_link, "preview", return_value={
                    "ok": True,
                    "url": "https://www.instagram.com/reel/Abc/",
                    "canonical": "https://www.instagram.com/reel/Abc/",
                    "title": "sophia (@productplaybook_)",
                    "caption": "Last chance for students.",
                    "author": "productplaybook_",
                    "site": "Instagram",
                    "image": "",
                    "media_type": "Vídeo",
                    "evidence": "caption",
                    "error": "",
                }):
                    created = capture(Namespace(
                        title="",
                        content="",
                        content_file=None,
                        type="Ideia",
                        status="Inbox",
                        topic=["Inspiração"],
                        source="",
                        url="",
                        from_url="https://www.instagram.com/reel/Abc/",
                        next_action="",
                        dry_run=False,
                    ), {"backend": "local"})
        self.assertTrue(created["created"])
        item = created["item"]
        self.assertEqual(item["type"], "Vídeo")
        self.assertIn("productplaybook_", item["title"])
        self.assertIn("Last chance", item["content"])
        self.assertEqual(item["source"], "https://www.instagram.com/reel/Abc/")


if __name__ == "__main__":
    unittest.main()
