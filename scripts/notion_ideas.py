#!/usr/bin/env python3
"""Capture and organize ideas in the owner's vault.

The owner chooses the backend at setup: their own Notion database, or a local
JSON file on this machine. Never someone else's Notion.

This script uses only the Python standard library. It never prints secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STATE_NAME = "weekly-picks-state.json"
SAVED_CONTEXT_NAME = "saved-context.json"
PICKS_CONFIG_NAME = "weekly-picks.json"
PICK_STATUSES = ("Inbox", "Explorar")
DONE_STATUSES = ("Concluída", "Arquivada", "Em andamento")
# Timing markers only. Life events (travel, wedding, moving, gifts) are
# owner-specific and live in saved-context.json after chat, not here.
LONG_TERM_TOPICS = {
    "algum dia",
    "later",
    "someday",
    "longo prazo",
    "not this week",
}
LONG_TERM_HINTS = (
    "algum dia",
    "longo prazo",
    "not this week",
    "não é pra agora",
    "nao e pra agora",
    "someday",
    "next year",
    "no próximo ano",
    "no proximo ano",
    "daqui a meses",
    "daqui a anos",
    "years from now",
    "in a few years",
    "not for now",
)
WEEK_FEASIBLE_HINTS = (
    "ouvir",
    "ler",
    "assistir",
    "escutar",
    "testar",
    "experimentar",
    "pesquisar",
    "comparar",
    "avaliar",
    "verificar",
    "conferir",
    "esta semana",
    "hoje",
    "15 min",
    "30 min",
    "1 hora",
    "rápid",
)
EASY_HINTS = ("ouvir", "ler", "assistir", "escutar", "verificar", "conferir", "15 min", "30 min")

API_BASE = "https://api.notion.com/v1"
VERSION = "2025-09-03"
DEFAULT_CONFIG_NAME = "notion-ideas.json"
LOCAL_VAULT_NAME = "vault.json"
TITLE_PROP = "Name"
CONTENT_PROP = "Conteúdo"
STATUS_OPTIONS = ("Inbox", "Explorar", "Em andamento", "Concluída", "Arquivada")
TYPE_OPTIONS = ("Ideia", "Link", "Texto", "Imagem", "PDF", "Vídeo")
REQUIRED_PROPERTIES = {
    TITLE_PROP: "title",
    CONTENT_PROP: "rich_text",
    "Status": "select",
    "Tipo": "select",
    "Temas": "multi_select",
    "Fonte": "url",
    "Capturado em": "date",
    "Próxima ação": "rich_text",
}
SELECT_OPTIONS = {
    "Status": STATUS_OPTIONS,
    "Tipo": TYPE_OPTIONS,
}


class NotionError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"Notion API {status} {code}: {message}")


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def load_key() -> str:
    key = os.environ.get("NOTION_API_KEY")
    if key:
        return key.strip()
    home = hermes_home()
    candidates = [home / ".env", home / ".hermes" / ".env"]
    candidates.extend(sorted(home.glob(".env.bak*"), reverse=True))
    for env_path in candidates:
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("NOTION_API_KEY="):
                value = stripped.split("=", 1)[1].strip()
                if value:
                    return value
    raise NotionError(0, "missing_token", "NOTION_API_KEY is not configured")


def saved_context_path() -> Path:
    custom = os.environ.get("SAVED_CONTEXT_CONFIG")
    if custom:
        return Path(custom)
    home = hermes_home()
    primary = home / SAVED_CONTEXT_NAME
    if primary.exists():
        return primary
    return home / PICKS_CONFIG_NAME


def load_picks_config() -> dict[str, Any]:
    path = saved_context_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_picks_config(config: dict[str, Any]) -> None:
    path = hermes_home() / SAVED_CONTEXT_NAME
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merged_excluded_topics(config: dict[str, Any]) -> set[str]:
    topics = {_fold(topic) for topic in config.get("excluded_topics", [])}
    topics |= {_fold(topic) for topic in config.get("dynamic_excluded_topics", [])}
    for fact in config.get("life_facts", []):
        if fact.get("weekly_effect") == "exclude":
            for topic in fact.get("topics", []):
                topics.add(_fold(str(topic)))
    return topics


def merged_excluded_substrings(config: dict[str, Any]) -> list[str]:
    values = list(config.get("excluded_topic_substrings", []))
    values.extend(config.get("excluded_content_substrings", []))
    for fact in config.get("life_facts", []):
        if fact.get("weekly_effect") == "exclude":
            values.extend(fact.get("keywords", []))
    return [_fold(str(value)) for value in values if value]


def owner_context_summary(config: dict[str, Any]) -> str:
    lines = []
    for fact in config.get("life_facts", []):
        text = str(fact.get("fact") or "").strip()
        if text:
            lines.append(text)
    legacy = str(config.get("owner_context") or "").strip()
    if legacy and legacy not in lines:
        lines.append(legacy)
    return " ".join(lines)


def load_config() -> dict[str, str]:
    path = Path(os.environ.get("NOTION_IDEAS_CONFIG", str(hermes_home() / DEFAULT_CONFIG_NAME)))
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NotionError(0, "missing_config", f"Missing config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NotionError(0, "invalid_config", f"Invalid config: {path}") from exc
    if not isinstance(config, dict):
        raise NotionError(0, "invalid_config", f"Invalid config: {path}")
    if is_local(config):
        return {"backend": "local"}
    for field in ("database_id", "data_source_id"):
        if not config.get(field):
            raise NotionError(0, "invalid_config", f"Missing config field: {field}")
        if str(config[field]).startswith("REPLACE_"):
            raise NotionError(
                0,
                "needs_setup",
                "No vault yet. This owner can choose local save, or connect THEIR Notion database.",
            )
    config["backend"] = "notion"
    return config


def is_local(config: dict[str, Any] | None = None) -> bool:
    if config is None:
        path = Path(os.environ.get("NOTION_IDEAS_CONFIG", str(hermes_home() / DEFAULT_CONFIG_NAME)))
        if not path.exists():
            return False
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
    return str((config or {}).get("backend") or "").strip().lower() == "local"


def vault_path() -> Path:
    custom = os.environ.get("SAVED_LOCAL_VAULT")
    if custom:
        return Path(custom)
    return hermes_home() / ".saved" / LOCAL_VAULT_NAME


def load_vault() -> list[dict[str, Any]]:
    path = vault_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items") if isinstance(data, dict) else data
    return list(items) if isinstance(items, list) else []


def save_vault(items: list[dict[str, Any]]) -> None:
    path = vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_local_id() -> str:
    return "local-" + uuid.uuid4().hex


def item_id(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith("local-"):
        return raw
    return notion_id(raw)


def has_key() -> bool:
    try:
        return bool(load_key())
    except NotionError:
        return False


def notion_id(value: str) -> str:
    tail = value.split("?")[0].rstrip("/").split("/")[-1]
    match = re.search(r"(?:^|-)([0-9a-fA-F]{32})$", tail)
    if match:
        raw = match.group(1).lower()
    else:
        compact = tail.replace("-", "")
        match = re.search(r"([0-9a-fA-F]{32})$", compact)
        if not match:
            raise NotionError(0, "invalid_id", "Expected a Notion page/database ID or URL")
        raw = match.group(1).lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def ids_look_valid(database_id: str, data_source_id: str) -> bool:
    try:
        return notion_id(database_id) == database_id and notion_id(data_source_id) == data_source_id
    except NotionError:
        return False


def setup_status() -> dict[str, Any]:
    path = Path(os.environ.get("NOTION_IDEAS_CONFIG", str(hermes_home() / DEFAULT_CONFIG_NAME)))
    config: dict[str, Any] = {}
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    if is_local(config):
        items = load_vault()
        return {
            "ready": True,
            "backend": "local",
            "has_token": False,
            "vault_path": str(vault_path()),
            "items": len(items),
            "config_path": str(path),
            "next": "Local vault is ready. Capture stays on this machine; it does not use anyone else's Notion.",
        }
    db = str(config.get("database_id") or "")
    ds = str(config.get("data_source_id") or "")
    placeholder = (not db) or db.startswith("REPLACE_") or (not ds) or ds.startswith("REPLACE_")
    valid = (not placeholder) and ids_look_valid(db, ds)
    token = has_key()
    ready = token and valid
    return {
        "ready": ready,
        "backend": "notion" if ready else "unset",
        "has_token": token,
        "has_database": bool(db) and not db.startswith("REPLACE_"),
        "has_data_source": bool(ds) and not ds.startswith("REPLACE_"),
        "ids_look_valid": valid,
        "database_name": config.get("database_name") or "",
        "config_path": str(path),
        "next": (
            "This owner's Notion is connected. Capture and weekly picks can run."
            if ready
            else "Ask THIS owner: local vault on this machine, or THEIR Notion (never someone else's). Local: setup-local. Notion: host .env token + setup-from-url with THEIR database link."
        ),
    }


def write_config(database_id: str, data_source_id: str, database_name: str) -> dict[str, Any]:
    path = Path(os.environ.get("NOTION_IDEAS_CONFIG", str(hermes_home() / DEFAULT_CONFIG_NAME)))
    config = {
        "backend": "notion",
        "database_id": notion_id(database_id),
        "data_source_id": notion_id(data_source_id),
        "database_name": (database_name or "Ideias").strip(),
    }
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "config_path": str(path), **config}


def setup_local(_args: argparse.Namespace | None = None) -> dict[str, Any]:
    path = Path(os.environ.get("NOTION_IDEAS_CONFIG", str(hermes_home() / DEFAULT_CONFIG_NAME)))
    config = {"backend": "local"}
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not vault_path().exists():
        save_vault([])
    return {
        "ok": True,
        "backend": "local",
        "config_path": str(path),
        "vault_path": str(vault_path()),
        "items": len(load_vault()),
    }


def setup_write(args: argparse.Namespace) -> dict[str, Any]:
    if str(args.database_id).startswith("REPLACE_") or str(args.data_source_id).startswith("REPLACE_"):
        raise NotionError(0, "needs_setup", "Those are placeholders. Use this owner's Notion IDs.")
    return write_config(args.database_id, args.data_source_id, args.database_name)


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {load_key()}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(API_BASE + path, data=data, headers=headers(), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
            code = str(body.get("code", "http_error"))
            message = str(body.get("message", "request failed"))
        except json.JSONDecodeError:
            code, message = "http_error", "request failed"
        raise NotionError(exc.code, code, message) from exc
    except urllib.error.URLError as exc:
        raise NotionError(0, "network_error", str(exc.reason)) from exc


def schema_report(source: dict[str, Any]) -> dict[str, Any]:
    props = source.get("properties") or {}
    missing: list[str] = []
    wrong: list[dict[str, str]] = []
    missing_opts: list[dict[str, Any]] = []
    for name, kind in REQUIRED_PROPERTIES.items():
        prop = props.get(name)
        if not prop:
            missing.append(name)
            continue
        actual = str(prop.get("type") or "")
        if actual != kind:
            wrong.append({"name": name, "expected": kind, "got": actual})
            continue
        wanted = SELECT_OPTIONS.get(name)
        if wanted:
            have = {item.get("name") for item in (prop.get(kind) or {}).get("options") or []}
            need = [option for option in wanted if option not in have]
            if need:
                missing_opts.append({"name": name, "missing": need})
    return {
        "missing_properties": missing,
        "wrong_types": wrong,
        "missing_options": missing_opts,
        "ok": not (missing or wrong or missing_opts),
    }


def property_create_payload(name: str) -> dict[str, Any]:
    kind = REQUIRED_PROPERTIES[name]
    if kind == "title":
        return {"title": {}}
    if kind == "rich_text":
        return {"rich_text": {}}
    if kind == "url":
        return {"url": {}}
    if kind == "date":
        return {"date": {}}
    if kind == "multi_select":
        return {"multi_select": {"options": []}}
    if kind == "select":
        return {"select": {"options": [{"name": option} for option in SELECT_OPTIONS[name]]}}
    raise NotionError(0, "invalid_config", f"unsupported property type for {name}")


def ensure_schema(config: dict[str, str], apply: bool = True) -> dict[str, Any]:
    source = api("GET", f"/data_sources/{config['data_source_id']}")
    report = schema_report(source)
    applied: list[str] = []
    if apply:
        patch: dict[str, Any] = {}
        for name in report["missing_properties"]:
            if name == TITLE_PROP:
                continue
            patch[name] = property_create_payload(name)
        props = source.get("properties") or {}
        for item in report["missing_options"]:
            name = item["name"]
            if name in patch or name not in props:
                continue
            kind = REQUIRED_PROPERTIES[name]
            current = [opt.get("name") for opt in (props[name].get(kind) or {}).get("options") or [] if opt.get("name")]
            for option in SELECT_OPTIONS[name]:
                if option not in current:
                    current.append(option)
            patch[name] = {kind: {"options": [{"name": option} for option in current]}}
        if patch:
            api("PATCH", f"/data_sources/{config['data_source_id']}", {"properties": patch})
            applied = list(patch)
            source = api("GET", f"/data_sources/{config['data_source_id']}")
            report = schema_report(source)
    report["applied"] = applied
    return report


def find_child_database(page_ident: str) -> str | None:
    cursor: str | None = None
    while True:
        path = f"/blocks/{page_ident}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        data = api("GET", path)
        for block in data.get("results") or []:
            if block.get("type") == "child_database":
                return block.get("id")
        if not data.get("has_more"):
            return None
        cursor = data.get("next_cursor")
        if not cursor:
            return None


def resolve_database(url: str) -> dict[str, str]:
    ident = notion_id(url)
    try:
        database = api("GET", f"/databases/{ident}")
    except NotionError as exc:
        if exc.status == 400 and "page, not a database" in (exc.message or ""):
            child = find_child_database(ident)
            if not child:
                raise NotionError(
                    0,
                    "not_a_database",
                    "That URL is a page, not a database. Send the database URL, or add a database on the page.",
                ) from exc
            database = api("GET", f"/databases/{child}")
        elif exc.status == 404:
            raise NotionError(
                404,
                "not_shared",
                "Database not visible. Share it with this integration via Notion Connections, then retry.",
            ) from exc
        else:
            raise
    sources = database.get("data_sources") or []
    if not sources or not sources[0].get("id"):
        raise NotionError(0, "no_data_source", "Database has no data_sources[0].id")
    title = "".join(item.get("plain_text", "") for item in database.get("title") or [])
    return {
        "database_id": database["id"],
        "data_source_id": sources[0]["id"],
        "database_name": title or "Ideias",
    }


def setup_from_url(args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_database(args.url)
    if args.dry_run:
        return {"dry_run": True, **resolved}
    written = write_config(resolved["database_id"], resolved["data_source_id"], resolved["database_name"])
    schema = ensure_schema(written, apply=not args.no_schema)
    health = doctor(written)
    return {**written, "schema": schema, "doctor": health}


def chunks(text: str, size: int = 1900) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or ([] if not text else [text])


def rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": part}} for part in chunks(text)]


def normalize_topics(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for raw in values or []:
        for value in raw.split(","):
            value = value.strip()
            if value and value not in result:
                result.append(value)
    return result


def plain_property(prop: dict[str, Any] | None) -> Any:
    if not prop:
        return None
    kind = prop.get("type")
    value = prop.get(kind, {})
    if kind in ("title", "rich_text"):
        return "".join(item.get("plain_text", "") for item in value or [])
    if kind == "select":
        return (value or {}).get("name")
    if kind == "multi_select":
        return [item.get("name") for item in value or []]
    if kind == "url":
        return value
    if kind == "date":
        return (value or {}).get("start")
    if kind == "checkbox":
        return value
    if kind == "number":
        return value
    return value


def item_from_page(page: dict[str, Any]) -> dict[str, Any]:
    props = page.get("properties", {})
    return {
        "id": page.get("id"),
        "url": page.get("url"),
        "title": plain_property(props.get(TITLE_PROP)) or "",
        "status": plain_property(props.get("Status")),
        "type": plain_property(props.get("Tipo")),
        "topics": plain_property(props.get("Temas")) or [],
        "source": plain_property(props.get("Fonte")),
        "captured_at": plain_property(props.get("Capturado em")),
        "next_action": plain_property(props.get("Próxima ação")) or "",
        "content": plain_property(props.get(CONTENT_PROP)) or "",
        "last_edited_time": page.get("last_edited_time"),
    }


def add_body(page_id: str, content: str) -> None:
    if not content:
        return
    blocks: list[dict[str, Any]] = []
    for part in chunks(content):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text(part)},
        })
    api("PATCH", f"/blocks/{page_id}/children", {"children": blocks})


def get_schema(config: dict[str, str]) -> dict[str, Any]:
    return api("GET", f"/data_sources/{config['data_source_id']}")


def ensure_topic_options(config: dict[str, str], topics: list[str]) -> None:
    if is_local(config) or not topics:
        return
    schema = get_schema(config)
    prop = (schema.get("properties") or {}).get("Temas")
    if not prop or prop.get("type") != "multi_select":
        return
    current = prop.get("multi_select", {}).get("options", [])
    existing = {item.get("name") for item in current}
    missing = [topic for topic in topics if topic not in existing]
    if not missing:
        return
    options = [{"name": item.get("name"), "color": item.get("color", "default")} for item in current]
    options.extend({"name": topic, "color": "default"} for topic in missing)
    api("PATCH", f"/data_sources/{config['data_source_id']}", {
        "properties": {"Temas": {"multi_select": {"options": options}}}
    })


def capture(args: argparse.Namespace, config: dict[str, str]) -> dict[str, Any]:
    content = args.content or ""
    if args.content_file:
        if args.content_file == "-":
            content = sys.stdin.read()
        else:
            content = Path(args.content_file).read_text(encoding="utf-8")
    topics = normalize_topics(args.topic)
    source = (getattr(args, "source", None) or getattr(args, "url", None) or "") or ""
    captured = datetime.now(timezone.utc)
    if is_local(config):
        item = {
            "id": new_local_id(),
            "url": "",
            "title": args.title,
            "status": args.status,
            "type": args.type,
            "topics": topics,
            "source": source or None,
            "captured_at": captured.date().isoformat(),
            "next_action": args.next_action or "",
            "content": content,
            "last_edited_time": captured.isoformat(),
        }
        if args.dry_run:
            return {"dry_run": True, "operation": "capture", "backend": "local", "item": item}
        items = load_vault()
        items.append(item)
        save_vault(items)
        return {"created": True, "backend": "local", "item": item}
    if not args.dry_run:
        ensure_topic_options(config, topics)
    props: dict[str, Any] = {
        TITLE_PROP: {"title": rich_text(args.title)},
        "Status": {"select": {"name": args.status}},
        "Tipo": {"select": {"name": args.type}},
        "Capturado em": {"date": {"start": datetime.now(timezone.utc).date().isoformat()}},
    }
    if topics:
        props["Temas"] = {"multi_select": [{"name": topic} for topic in topics]}
    if source:
        props["Fonte"] = {"url": source}
    if args.next_action:
        props["Próxima ação"] = {"rich_text": rich_text(args.next_action)}
    if content:
        props[CONTENT_PROP] = {"rich_text": rich_text(content)}
    payload = {"parent": {"database_id": config["database_id"]}, "properties": props}
    if args.dry_run:
        return {"dry_run": True, "operation": "capture", "payload": payload}
    page = api("POST", "/pages", payload)
    add_body(page["id"], content)
    return {"created": True, "item": item_from_page(page)}


def query_all(config: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        result = api("POST", f"/data_sources/{config['data_source_id']}/query", payload)
        rows.extend(result.get("results", []))
        if not result.get("has_more"):
            return rows
        cursor = result.get("next_cursor")
        if not cursor:
            return rows


def list_items(config: dict[str, str]) -> list[dict[str, Any]]:
    if is_local(config):
        return load_vault()
    return [item_from_page(page) for page in query_all(config)]


def search(args: argparse.Namespace, config: dict[str, str]) -> dict[str, Any]:
    needle = (args.query or "").casefold().strip()
    items = list_items(config)
    if needle:
        items = [
            item for item in items
            if needle in json.dumps(item, ensure_ascii=False).casefold()
        ]
    return {"count": min(len(items), args.limit), "items": items[: args.limit], "backend": "local" if is_local(config) else "notion"}


def page_id(value: str) -> str:
    return item_id(value)


def organize(args: argparse.Namespace, config: dict[str, str]) -> dict[str, Any]:
    ident = page_id(args.page)
    if is_local(config):
        items = load_vault()
        current = next((item for item in items if item.get("id") == ident), None)
        if not current:
            raise NotionError(0, "not_found", f"No local item {ident}")
        changed = False
        if args.status:
            current["status"] = args.status
            changed = True
        if args.type:
            current["type"] = args.type
            changed = True
        if args.next_action is not None:
            current["next_action"] = args.next_action
            changed = True
        add_topics = normalize_topics(args.add_topic)
        remove_topics = set(normalize_topics(args.remove_topic))
        if add_topics or remove_topics:
            topics = [topic for topic in current.get("topics") or [] if topic not in remove_topics]
            for topic in add_topics:
                if topic not in topics:
                    topics.append(topic)
            current["topics"] = topics
            changed = True
        if not changed:
            raise NotionError(0, "no_changes", "Provide at least one organization change")
        current["last_edited_time"] = datetime.now(timezone.utc).isoformat()
        save_vault(items)
        return {"updated": True, "backend": "local", "item": current}
    page = api("GET", f"/pages/{ident}")
    current = item_from_page(page)
    updates: dict[str, Any] = {}
    if args.status:
        updates["Status"] = {"select": {"name": args.status}}
    if args.type:
        updates["Tipo"] = {"select": {"name": args.type}}
    if args.next_action is not None:
        updates["Próxima ação"] = {"rich_text": rich_text(args.next_action)}
    add_topics = normalize_topics(args.add_topic)
    remove_topics = set(normalize_topics(args.remove_topic))
    if add_topics or remove_topics:
        topics = [topic for topic in current.get("topics", []) if topic not in remove_topics]
        for topic in add_topics:
            if topic not in topics:
                topics.append(topic)
        ensure_topic_options(config, topics)
        updates["Temas"] = {"multi_select": [{"name": topic} for topic in topics]}
    if not updates:
        raise NotionError(0, "no_changes", "Provide at least one organization change")
    updated = api("PATCH", f"/pages/{ident}", {"properties": updates})
    return {"updated": True, "item": item_from_page(updated)}


def _fold(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return folded.casefold()


def state_path() -> Path:
    return hermes_home() / ".saved" / STATE_NAME


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"history": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"history": []}


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recently_picked(item_id: str | None, state: dict[str, Any], weeks: int = 2) -> bool:
    if not item_id:
        return False
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=7 * weeks)
    for entry in state.get("history", []):
        try:
            run_day = datetime.fromisoformat(str(entry.get("run_at", ""))[:10]).date()
        except ValueError:
            continue
        if run_day < cutoff:
            continue
        if item_id in (entry.get("ids") or []):
            return True
    return False


def item_blob(item: dict[str, Any]) -> str:
    return _fold(
        " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("content") or ""),
                str(item.get("next_action") or ""),
                " ".join(item.get("topics") or []),
            ]
        )
    )


def is_long_term(item: dict[str, Any], picks_config: dict[str, Any] | None = None) -> str | None:
    picks_config = picks_config or {}
    item_id = item.get("id")
    if item_id and item_id in set(picks_config.get("deferred_item_ids", [])):
        return "owner pediu para deixar para depois"
    topics_raw = item.get("topics") or []
    topics = {_fold(topic) for topic in topics_raw}
    excluded_topics = merged_excluded_topics(picks_config) | LONG_TERM_TOPICS
    for topic in topics:
        if topic in excluded_topics:
            return f"tema de longo prazo: {topic}"
        for hint in merged_excluded_substrings(picks_config) + list(LONG_TERM_TOPICS):
            if hint in topic:
                return f"tema de longo prazo: {topic}"
    blob = item_blob(item)
    for hint in merged_excluded_substrings(picks_config) + [_fold(h) for h in LONG_TERM_HINTS]:
        if hint in blob:
            return f"parece fora desta semana ({hint})"
    return None


def week_feasible_score(item: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    blob = item_blob(item)
    status = item.get("status")
    if status == "Inbox":
        score += 2
        reasons.append("inbox")
    elif status == "Explorar":
        score += 1
        reasons.append("explorar")
    for hint in WEEK_FEASIBLE_HINTS:
        if hint in blob:
            score += 2
            reasons.append(f"ação curta ({hint})")
            break
    next_action = _fold(str(item.get("next_action") or ""))
    if next_action and len(next_action) <= 120:
        score += 1
        reasons.append("próxima ação concreta")
    captured = item.get("captured_at")
    if captured:
        try:
            age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(captured).date()).days
            if age <= 14:
                score += 1
                reasons.append("recente")
        except ValueError:
            pass
    if any(hint in blob for hint in ("comprar passagem", "reservar hotel", "mudar de país", "financiar")):
        score -= 8
        reasons.append("parece grande para uma semana")
    return score, reasons


def pick_bucket(item: dict[str, Any], score: int) -> str:
    blob = item_blob(item)
    if any(hint in blob for hint in EASY_HINTS):
        return "easy"
    if score >= 5:
        return "meaningful"
    return "exploratory"


def weekly_picks(args: argparse.Namespace, config: dict[str, str]) -> dict[str, Any]:
    state = load_state()
    picks_config = load_picks_config()
    items = list_items(config)
    excluded: list[dict[str, str]] = []
    candidates: list[dict[str, Any]] = []
    for item in items:
        status = item.get("status")
        if status in DONE_STATUSES:
            excluded.append({"id": item.get("id", ""), "title": item.get("title", ""), "reason": f"status {status}"})
            continue
        if status not in PICK_STATUSES:
            excluded.append({"id": item.get("id", ""), "title": item.get("title", ""), "reason": f"status {status}"})
            continue
        long_term = is_long_term(item, picks_config)
        if long_term:
            excluded.append({"id": item.get("id", ""), "title": item.get("title", ""), "reason": long_term})
            continue
        if recently_picked(item.get("id"), state, weeks=args.cooldown_weeks):
            excluded.append({"id": item.get("id", ""), "title": item.get("title", ""), "reason": "escolhida nas últimas semanas"})
            continue
        score, reasons = week_feasible_score(item)
        if score < 1:
            excluded.append({"id": item.get("id", ""), "title": item.get("title", ""), "reason": "pouco acionável nesta semana"})
            continue
        candidates.append({
            **item,
            "score": score,
            "reasons": reasons,
            "bucket": pick_bucket(item, score),
        })

    candidates.sort(key=lambda row: (-row["score"], row.get("title") or ""))
    picks: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for bucket in ("easy", "meaningful", "exploratory"):
        for row in candidates:
            if row.get("id") in used_ids:
                continue
            if row.get("bucket") != bucket:
                continue
            picks.append(row)
            used_ids.add(row.get("id") or "")
            break
    for row in candidates:
        if len(picks) >= args.count:
            break
        if row.get("id") in used_ids:
            continue
        picks.append(row)
        used_ids.add(row.get("id") or "")

    result = {
        "week": datetime.now(timezone.utc).date().isoformat(),
        "count": len(picks),
        "picks": [
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "url": row.get("url"),
                "status": row.get("status"),
                "topics": row.get("topics"),
                "next_action": row.get("next_action"),
                "bucket": row.get("bucket"),
                "score": row.get("score"),
                "reasons": row.get("reasons"),
            }
            for row in picks[: args.count]
        ],
        "excluded_long_term": sum(
            1 for row in excluded
            if "longo prazo" in row.get("reason", "") or "fora desta semana" in row.get("reason", "")
        ),
        "excluded_total": len(excluded),
        "not_saved_this_week": True,
        "owner_context": owner_context_summary(picks_config),
        "life_facts": picks_config.get("life_facts", []),
    }
    if args.mark and picks and not args.dry_run:
        state.setdefault("history", []).append({
            "run_at": datetime.now(timezone.utc).isoformat(),
            "ids": [row.get("id") for row in picks if row.get("id")],
        })
        state["history"] = state["history"][-26:]
        state["last_run"] = result["week"]
        save_state(state)
        result["marked"] = True
    return result


def context_show(_args: argparse.Namespace) -> dict[str, Any]:
    config = load_picks_config()
    return {
        "life_facts": config.get("life_facts", []),
        "dynamic_excluded_topics": config.get("dynamic_excluded_topics", []),
        "deferred_item_ids": config.get("deferred_item_ids", []),
        "owner_context": owner_context_summary(config),
        "path": str(saved_context_path()),
    }


def context_remember(args: argparse.Namespace) -> dict[str, Any]:
    fact = (args.fact or "").strip()
    if not fact:
        raise NotionError(0, "missing_fact", "Provide --fact with what the owner said")
    config = load_picks_config()
    entry = {
        "fact": fact,
        "weekly_effect": args.effect,
        "topics": normalize_topics(args.topic),
        "keywords": normalize_topics(args.keyword),
        "since": datetime.now(timezone.utc).date().isoformat(),
        "source": "chat",
    }
    config.setdefault("life_facts", []).append(entry)
    if args.effect == "exclude":
        for topic in entry["topics"]:
            dynamic = config.setdefault("dynamic_excluded_topics", [])
            if topic not in dynamic:
                dynamic.append(topic)
    save_picks_config(config)
    return {"remembered": True, "entry": entry}


def context_defer(args: argparse.Namespace, config: dict[str, str]) -> dict[str, Any]:
    ident = page_id(args.page)
    reason = (args.reason or "owner pediu para deixar para depois").strip()
    org_args = argparse.Namespace(
        page=ident,
        status="Explorar",
        type=None,
        add_topic=["Algum dia"],
        remove_topic=None,
        next_action=reason,
    )
    updated = organize(org_args, config)
    picks_config = load_picks_config()
    deferred = picks_config.setdefault("deferred_item_ids", [])
    if ident not in deferred:
        deferred.append(ident)
    picks_config.setdefault("life_facts", []).append({
        "fact": f"Ideia adiada pelo owner: {updated['item'].get('title', ident)} — {reason}",
        "weekly_effect": "exclude",
        "topics": updated["item"].get("topics", []),
        "keywords": [],
        "since": datetime.now(timezone.utc).date().isoformat(),
        "source": "defer",
        "item_id": ident,
    })
    save_picks_config(picks_config)
    return {"deferred": True, "item": updated["item"], "reason": reason}


def doctor(config: dict[str, str]) -> dict[str, Any]:
    if is_local(config):
        path = vault_path()
        items = load_vault()
        return {
            "ok": True,
            "backend": "local",
            "vault_path": str(path),
            "items": len(items),
            "writable": os.access(path.parent, os.W_OK),
            "fix": None,
        }
    me = api("GET", "/users/me")
    database = api("GET", f"/databases/{config['database_id']}")
    source = api("GET", f"/data_sources/{config['data_source_id']}")
    query = api("POST", f"/data_sources/{config['data_source_id']}/query", {"page_size": 1})
    schema = schema_report(source)
    return {
        "ok": bool(me.get("object") == "user" and me.get("type") == "bot" and schema["ok"]),
        "backend": "notion",
        "authenticated": me.get("object") == "user" and me.get("type") == "bot",
        "bot_name_present": bool(me.get("name")),
        "database_title": "".join(x.get("plain_text", "") for x in database.get("title", [])),
        "data_source_id": source.get("id"),
        "property_names": list((source.get("properties") or {}).keys()),
        "schema": schema,
        "query_ok": True,
        "rows_sampled": len(query.get("results", [])),
        "fix": (
            None
            if schema["ok"]
            else "Create the missing properties or run: python3 notion_ideas.py setup-from-url <database-url>"
        ),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Capture and organize items in this owner's Saved vault (local or their Notion).")
    sub = p.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="Create one item in the Ideias database")
    cap.add_argument("title")
    cap.add_argument("--content", default="")
    cap.add_argument("--content-file", help="Read full content from a file, or - for stdin")
    cap.add_argument("--type", choices=TYPE_OPTIONS, default="Ideia")
    cap.add_argument("--status", choices=STATUS_OPTIONS, default="Inbox")
    cap.add_argument("--topic", action="append", help="Topic; can be repeated or comma-separated")
    cap.add_argument("--source", default="")
    cap.add_argument("--url", dest="url", default="", help="Alias for --source")
    cap.add_argument("--next-action", default="")
    cap.add_argument("--dry-run", action="store_true")

    sea = sub.add_parser("search", help="Search items by title, content, metadata, or URL")
    sea.add_argument("query", nargs="?", default="")
    sea.add_argument("--limit", type=int, default=50)

    org = sub.add_parser("organize", help="Update status, type, topics, or next action")
    org.add_argument("page")
    org.add_argument("--status", choices=STATUS_OPTIONS)
    org.add_argument("--type", choices=TYPE_OPTIONS)
    org.add_argument("--add-topic", action="append")
    org.add_argument("--remove-topic", action="append")
    org.add_argument("--next-action")

    wk = sub.add_parser("weekly-picks", help="Pick ideas explorable this week")
    wk.add_argument("--count", type=int, default=3)
    wk.add_argument("--cooldown-weeks", type=int, default=2)
    wk.add_argument("--mark", action="store_true", help="Record picks so they are not repeated soon")
    wk.add_argument("--dry-run", action="store_true")

    ctx = sub.add_parser("context", help="Remember owner timeline and defer items from chat")
    ctx_sub = ctx.add_subparsers(dest="context_command", required=True)
    ctx_sub.add_parser("show", help="Show remembered owner context for weekly picks")
    rem = ctx_sub.add_parser("remember", help="Store a life fact from conversation")
    rem.add_argument("--fact", required=True)
    rem.add_argument(
        "--effect",
        choices=("exclude", "note"),
        default="note",
        help="exclude removes matching topics from weekly picks; note is context only",
    )
    rem.add_argument("--topic", action="append", help="Notion topic affected by this fact")
    rem.add_argument("--keyword", action="append", help="Extra keyword to treat as long-term")
    defer = ctx_sub.add_parser("defer", help="Mark one Notion item as not for now")
    defer.add_argument("page")
    defer.add_argument("--reason", default="")

    sub.add_parser("doctor", help="Verify the chosen vault (local file or Notion)")
    sub.add_parser("setup-status", help="Whether THIS owner has chosen a vault (no secrets)")
    sub.add_parser("setup-local", help="Save on this machine; do not use Notion")
    sw = sub.add_parser("setup-write", help="Save THIS owner's Notion database IDs")
    sw.add_argument("--database-id", required=True)
    sw.add_argument("--data-source-id", required=True)
    sw.add_argument("--database-name", default="Ideias")
    sf = sub.add_parser("setup-from-url", help="Connect THIS owner's database from a Notion URL")
    sf.add_argument("url")
    sf.add_argument("--dry-run", action="store_true")
    sf.add_argument("--no-schema", action="store_true", help="Do not create missing properties")
    return p


def main() -> int:
    try:
        args = parser().parse_args()
        if args.command == "setup-status":
            result = setup_status()
        elif args.command == "setup-write":
            result = setup_write(args)
        elif args.command == "setup-from-url":
            result = setup_from_url(args)
        elif args.command == "setup-local":
            result = setup_local(args)
        elif args.command == "context" and args.context_command in ("show", "remember"):
            result = context_show(args) if args.context_command == "show" else context_remember(args)
        else:
            config = load_config()
            if args.command == "capture":
                result = capture(args, config)
            elif args.command == "search":
                result = search(args, config)
            elif args.command == "organize":
                result = organize(args, config)
            elif args.command == "weekly-picks":
                result = weekly_picks(args, config)
            elif args.command == "context":
                result = context_defer(args, config)
            else:
                result = doctor(config)
        print(json.dumps(result, ensure_ascii=False))
        if args.command == "doctor" and isinstance(result, dict) and result.get("ok") is False:
            return 2
        return 0
    except NotionError as exc:
        print(json.dumps({"error": exc.code, "status": exc.status, "message": exc.message}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": "local_error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
