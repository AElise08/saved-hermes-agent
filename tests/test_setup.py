#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from notion_ideas import (  # noqa: E402
    REQUIRED_PROPERTIES,
    ids_look_valid,
    notion_id,
    schema_report,
    setup_status,
)
import saved_config  # noqa: E402


class NotionIdTests(unittest.TestCase):
    def test_from_app_url(self):
        url = (
            "https://app.notion.com/p/"
            "Saved-teste-de-install-limpo-13-set-2026-3da996f0634c81aa93f4f6df302971f4"
        )
        self.assertEqual(notion_id(url), "3da996f0-634c-81aa-93f4-f6df302971f4")

    def test_rejects_garbage(self):
        with self.assertRaises(Exception):
            notion_id("not-a-notion-id")

    def test_ids_look_valid(self):
        good = "3da996f0-634c-81aa-93f4-f6df302971f4"
        self.assertTrue(ids_look_valid(good, good))
        self.assertFalse(ids_look_valid("REPLACE_WITH_YOUR_NOTION_DATABASE_ID", good))


class SchemaReportTests(unittest.TestCase):
    def test_missing_and_wrong_type(self):
        report = schema_report({"properties": {"Name": {"type": "title"}}})
        self.assertFalse(report["ok"])
        self.assertIn("Conteúdo", report["missing_properties"])
        self.assertEqual(set(REQUIRED_PROPERTIES) - {"Name"}, set(report["missing_properties"]))

    def test_ok_when_complete(self):
        props = {
            "Name": {"type": "title"},
            "Conteúdo": {"type": "rich_text"},
            "Status": {"type": "select", "select": {"options": [{"name": n} for n in ("Inbox", "Explorar", "Em andamento", "Concluída", "Arquivada")]}},
            "Tipo": {"type": "select", "select": {"options": [{"name": n} for n in ("Ideia", "Link", "Texto", "Imagem", "PDF", "Vídeo")]}},
            "Temas": {"type": "multi_select", "multi_select": {"options": []}},
            "Fonte": {"type": "url"},
            "Capturado em": {"type": "date"},
            "Próxima ação": {"type": "rich_text"},
        }
        self.assertTrue(schema_report({"properties": props})["ok"])


class SetupStatusTests(unittest.TestCase):
    def test_placeholder_home_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "notion-ideas.json").write_text(json.dumps({
                "database_id": "REPLACE_WITH_YOUR_NOTION_DATABASE_ID",
                "data_source_id": "REPLACE_WITH_YOUR_NOTION_DATA_SOURCE_ID",
                "database_name": "Ideias",
            }))
            with patch.dict(os.environ, {"HERMES_HOME": tmp}, clear=False):
                os.environ.pop("NOTION_API_KEY", None)
                status = setup_status()
            self.assertFalse(status["ready"])
            self.assertFalse(status["has_token"])
            self.assertNotIn("ntn_", json.dumps(status))
            self.assertIn("Guardar aqui na máquina, ou no Notion?", status["next"])


class LocalVaultTests(unittest.TestCase):
    def test_setup_local_capture_search_without_notion(self):
        from argparse import Namespace
        from notion_ideas import capture, search, setup_local

        with tempfile.TemporaryDirectory() as tmp:
            env = {"HERMES_HOME": tmp}
            os.environ.pop("NOTION_API_KEY", None)
            with patch.dict(os.environ, env, clear=False):
                setup = setup_local()
                self.assertTrue(setup["ok"])
                self.assertEqual(setup["backend"], "local")
                status = setup_status()
                self.assertTrue(status["ready"])
                self.assertEqual(status["backend"], "local")
                created = capture(Namespace(
                    title="nota de voz",
                    content="consegue salvar?",
                    content_file=None,
                    type="Ideia",
                    status="Inbox",
                    topic=["teste"],
                    source="",
                    url="",
                    next_action="",
                    dry_run=False,
                ), {"backend": "local"})
                self.assertTrue(created["created"])
                self.assertTrue(str(created["item"]["id"]).startswith("local-"))
                found = search(Namespace(query="voz", limit=10), {"backend": "local"})
                self.assertEqual(found["count"], 1)
                self.assertEqual(found["backend"], "local")


class TimezoneTests(unittest.TestCase):
    def test_json_wins_over_compose_utc(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "saved-settings.json").write_text(json.dumps({
                "timezone": "America/Belem",
                "weekly_weekday": 6,
                "weekly_hour": 14,
            }))
            with patch.dict(os.environ, {"HERMES_HOME": tmp, "TZ": "UTC"}, clear=False):
                self.assertEqual(saved_config.timezone_name(), "America/Belem")

    def test_set_locale_from_pt_br(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("SAVED_LOCALE", None)
            with patch.dict(os.environ, {"HERMES_HOME": tmp}, clear=False):
                self.assertEqual(saved_config.locale(), "en")
                saved_config.set_locale("pt-BR")
                self.assertEqual(saved_config.locale(), "pt")
                saved = json.loads(Path(tmp, "saved-settings.json").read_text())
                self.assertEqual(saved["locale"], "pt")


if __name__ == "__main__":
    unittest.main()
