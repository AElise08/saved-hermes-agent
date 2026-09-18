#!/usr/bin/env python3
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from notion_ideas import (  # noqa: E402
    NotionError,
    capture,
    feedback,
    load_key,
    load_state,
    setup_guide,
    setup_local,
    setup_token,
    weekly_picks,
)

LOCAL = {"backend": "local"}


def make_capture(title, topic):
    return Namespace(
        title=title,
        content="",
        content_file=None,
        type="Ideia",
        status="Inbox",
        topic=[topic],
        source="",
        url="",
        next_action="ouvir hoje",
        dry_run=False,
    )


def picks():
    return weekly_picks(Namespace(count=3, cooldown_weeks=2, mark=False, dry_run=True), LOCAL)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {"HERMES_HOME": self.tmp.name}, clear=False)
        self.patch.start()
        os.environ.pop("NOTION_API_KEY", None)
        setup_local()
        self.a = capture(make_capture("podcast de história", "história"), LOCAL)["item"]
        self.b = capture(make_capture("curso de piano", "música"), LOCAL)["item"]

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_liked_boosts_topic(self):
        out = feedback(Namespace(item=self.a["id"], verdict="liked", reason=""), LOCAL)
        self.assertEqual(out["feedback"], "liked")
        state = load_state()
        self.assertIn("historia", state["feedback"]["liked_topics"])
        again = picks()
        boosted = next(row for row in again["picks"] if row["id"] == self.a["id"])
        self.assertIn("owner curtiu esse tema", boosted["reasons"])

    def test_skipped_rests_item_and_cools_topic(self):
        feedback(Namespace(item=self.b["id"], verdict="skipped", reason=""), LOCAL)
        again = picks()
        ids = [row["id"] for row in again["picks"]]
        self.assertNotIn(self.b["id"], ids)
        state = load_state()
        self.assertIn("musica", state["feedback"]["skipped_topics"])

    def test_done_and_later_change_status(self):
        done = feedback(Namespace(item=self.a["id"], verdict="done", reason=""), LOCAL)
        self.assertEqual(done["item"]["status"], "Concluída")
        later = feedback(Namespace(item=self.b["id"], verdict="later", reason="semana cheia"), LOCAL)
        self.assertTrue(later["deferred"])
        self.assertEqual(later["item"]["status"], "Explorar")

    def test_unknown_item_fails_without_touching_vault(self):
        with self.assertRaises(NotionError):
            feedback(Namespace(item="local-does-not-exist", verdict="liked", reason=""), LOCAL)

    def test_setup_guide_teaches_without_secrets(self):
        for locale in ("pt", "en"):
            guide = setup_guide(Namespace(locale=locale))
            self.assertTrue(guide["local_first"])
            self.assertGreaterEqual(len(guide["steps"]), 3)
            self.assertNotRegex(json.dumps(guide), r"ntn_[A-Za-z0-9]{10,}")


class SetupTokenTests(unittest.TestCase):
    def test_chat_secret_is_stored_private_and_never_echoed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HERMES_HOME": tmp}, clear=False):
                os.environ.pop("NOTION_API_KEY", None)
                secret = "ntn_" + "x" * 40
                out = setup_token(Namespace(key=secret))
                self.assertTrue(out["has_token"])
                self.assertNotIn(secret, json.dumps(out))
                path = Path(out["token_path"])
                self.assertTrue(path.exists())
                self.assertEqual(path.read_text(encoding="utf-8").strip(), secret)
                if hasattr(os, "chmod"):
                    self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
                self.assertEqual(load_key(), secret)

    def test_non_secret_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HERMES_HOME": tmp}, clear=False):
                for bad in ("https://www.notion.so/abc123", "short", ""):
                    with self.assertRaises(NotionError):
                        setup_token(Namespace(key=bad))


if __name__ == "__main__":
    unittest.main()
