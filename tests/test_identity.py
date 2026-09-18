#!/usr/bin/env python3
"""Identity answers must describe Saved concretely, never generically."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOUL = (ROOT / "runtime" / "SOUL.md").read_text(encoding="utf-8")
SKILL = (ROOT / "skills" / "saved" / "SKILL.md").read_text(encoding="utf-8")


class IdentityTests(unittest.TestCase):
    def test_soul_answers_who_and_what_concretely(self):
        for bit in (
            "o que você faz?",
            "como funciona?",
            "what do you do?",
            "who are you?",
            "teu cofre de ideias",
            "your idea vault",
            "3 ideias que dá pra explorar agora",
            "3 ideas you can actually explore now",
            "aqui na máquina, ou no Notion",
            "on this machine, or in Notion",
        ):
            self.assertIn(bit, SOUL)

    def test_soul_forbids_generic_assistant_talk(self):
        self.assertIn("never as a generic AI assistant", SOUL)

    def test_skill_loads_on_identity_questions(self):
        for bit in ("o que", "what do you do?", "who are you?", "how you work"):
            self.assertIn(bit, SKILL)
        self.assertIn("## Identity", SKILL)


if __name__ == "__main__":
    unittest.main()
