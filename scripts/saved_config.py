#!/usr/bin/env python3
"""Owner-specific Saved settings: timezone, weekly window, digest locale.

Nothing here assumes a country, a wedding, or a trip. Those belong in
saved-context.json after the owner says so in chat.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from send_chat import hermes_home

SETTINGS_NAME = "saved-settings.json"


def settings_path() -> Path:
    return hermes_home() / SETTINGS_NAME


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def timezone_name(data: dict | None = None) -> str:
    data = data if data is not None else load_settings()
    # Owner JSON wins. Compose often exports TZ=UTC, which would otherwise
    # ignore a timezone saved in chat.
    name = (str(data.get("timezone") or "").strip() or os.environ.get("TZ") or "UTC").strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return name or "UTC"


def zone(data: dict | None = None) -> ZoneInfo:
    return ZoneInfo(timezone_name(data))


def weekly_weekday(data: dict | None = None) -> int:
    """0 = Monday ... 6 = Sunday."""
    data = data if data is not None else load_settings()
    try:
        value = int(os.environ.get("SAVED_WEEKLY_WEEKDAY") or data.get("weekly_weekday", 6))
    except (TypeError, ValueError):
        value = 6
    return value if 0 <= value <= 6 else 6


def weekly_hour(data: dict | None = None) -> int:
    data = data if data is not None else load_settings()
    try:
        value = int(os.environ.get("SAVED_WEEKLY_HOUR") or data.get("weekly_hour", 14))
    except (TypeError, ValueError):
        value = 14
    return value if 0 <= value <= 23 else 14


def weekly_window_minutes(data: dict | None = None) -> int:
    data = data if data is not None else load_settings()
    try:
        value = int(data.get("weekly_window_minutes", 10))
    except (TypeError, ValueError):
        value = 10
    return value if 1 <= value <= 59 else 10


def normalize_locale(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw.startswith("pt"):
        return "pt"
    if raw.startswith("en"):
        return "en"
    return None


def locale(data: dict | None = None) -> str:
    data = data if data is not None else load_settings()
    return normalize_locale(os.environ.get("SAVED_LOCALE") or data.get("locale")) or "en"


def write_settings(updates: dict) -> dict:
    data = load_settings()
    data.update(updates)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def set_locale(value: str) -> dict:
    loc = normalize_locale(value)
    if loc is None:
        raise ValueError("locale must be pt or en")
    return write_settings({"locale": loc})


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Read or write this owner's Saved settings.")
    sub = parser.add_subparsers(dest="command", required=True)
    sl = sub.add_parser("set-locale", help="pt or en — used for weekly digest copy")
    sl.add_argument("locale")
    sub.add_parser("show", help="Print timezone, weekly hour, and locale")
    args = parser.parse_args()
    if args.command == "set-locale":
        try:
            data = set_locale(args.locale)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "locale": data.get("locale")}, ensure_ascii=False))
        return 0
    settings = load_settings()
    print(json.dumps({
        "timezone": timezone_name(settings),
        "weekly_weekday": weekly_weekday(settings),
        "weekly_hour": weekly_hour(settings),
        "locale": locale(settings),
        "path": str(settings_path()),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
