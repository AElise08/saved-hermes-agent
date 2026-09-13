#!/usr/bin/env python3
"""Format weekly Notion idea picks for Plow Chat delivery."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from saved_config import locale
from send_chat import send

SCRIPT = Path(__file__).with_name("notion_ideas.py")
COPY = {
    "en": {
        "title": "Saved — 3 ideas to explore this week",
        "subtitle": "(not everything you saved — only what you can do now)",
        "fallback_action": "Take a quick look and decide whether to go deeper.",
        "no_title": "Untitled",
        "excluded": "I left out {n} idea(s) you marked for later.",
        "swap": "Want to swap any?",
        "buckets": {"easy": "quick", "meaningful": "high impact", "exploratory": "new"},
        "now": "for now",
    },
    "pt": {
        "title": "Saved — 3 ideias para explorar esta semana",
        "subtitle": "(não é a lista do que você salvou — só o que dá para fazer agora)",
        "fallback_action": "Dar uma olhada rápida e decidir se vale aprofundar.",
        "no_title": "Sem título",
        "excluded": "Deixei de fora {n} ideia(s) que você marcou para depois.",
        "swap": "Quer trocar alguma?",
        "buckets": {"easy": "rápida", "meaningful": "com impacto", "exploratory": "nova"},
        "now": "para agora",
    },
}


def main() -> int:
    text = COPY[locale()]
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "weekly-picks", "--mark"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return proc.returncode
    data = json.loads(proc.stdout)
    picks = data.get("picks") or []
    if not picks:
        print("[SILENT]")
        return 0

    lines = [text["title"], text["subtitle"], ""]
    buckets = text["buckets"]
    for index, pick in enumerate(picks, start=1):
        label = buckets.get(pick.get("bucket"), text["now"])
        title = pick.get("title") or text["no_title"]
        action = (pick.get("next_action") or "").strip() or text["fallback_action"]
        lines.append(f"{index}. {title} ({label})")
        lines.append(f"   → {action}")
        if pick.get("url"):
            lines.append(f"   {pick['url']}")
        lines.append("")

    excluded = int(data.get("excluded_long_term") or 0)
    if excluded:
        lines.append(text["excluded"].format(n=excluded))
        lines.append(text["swap"])
    message = "\n".join(lines).rstrip()
    send(message)
    print(f"sent {len(message)} chars to plow chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
