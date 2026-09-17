#!/usr/bin/env python3
"""Fetch public caption/title for a link before Saved archives it.

Usage: preview_link.py <url>

Instagram/TikTok/YouTube often hide the reel from a normal browser UA.
Crawler UAs still receive Open Graph tags: caption, author, poster. This is
metadata, not a watch of the video. Stdlib only — same as the rest of Saved.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENTS = (
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
    "WhatsApp/2.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)

META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
ATTR = re.compile(
    r"""([^\s=]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))""",
    re.I,
)
INSTAGRAM_DESC = re.compile(
    r"""^\s*[\d,]+\s+likes(?:,\s*[\d,]+\s+comments)?\s*-\s*(\S+)\s+on\s+[^:]+:\s*\"?(.*)\"?\s*$""",
    re.I | re.S,
)
IG_TITLE_AUTHOR = re.compile(
    r"""^(.*?)\s+on Instagram:\s*\"?(.*)\"?\s*$""",
    re.I | re.S,
)
JSON_LD = re.compile(
    r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(.*?)</script>""",
    re.I | re.S,
)
OEMBED_LINK = re.compile(
    r"""<link[^>]+type=["']application/(?:json\+oembed|xml\+oembed)["'][^>]*>""",
    re.I,
)
TWITTER_AUTHOR = re.compile(r"^(.*?)\s*\(@([^)]+)\)")

HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
}


def canonical_url(value: str) -> str:
    raw = (value or "").strip().replace("\\", "")
    if not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return raw
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    drop = {k for k, _v in query if k.lower().startswith("utm_") or k.lower() in {"igsh", "igshid", "fbclid", "si"}}
    kept = [(k, v) for k, v in query if k not in drop]
    cleaned = parsed._replace(query=urllib.parse.urlencode(kept), fragment="")
    return urllib.parse.urlunsplit(cleaned)


def _attrs(tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in ATTR.finditer(tag):
        key = match.group(1).strip().lower()
        val = match.group(2) or match.group(3) or match.group(4) or ""
        out[key] = html_lib.unescape(val).strip()
    return out


def parse_meta(page: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for tag in META_TAG.findall(page or ""):
        attrs = _attrs(tag)
        prop = (attrs.get("property") or attrs.get("name") or "").strip().lower()
        content = attrs.get("content") or ""
        if prop and content and prop not in found:
            found[prop] = content
    title = re.search(r"<title[^>]*>(.*?)</title>", page or "", re.I | re.S)
    if title and "title" not in found:
        found["title"] = html_lib.unescape(re.sub(r"\s+", " ", title.group(1)).strip())
    return found


def parse_json_ld(page: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for block in JSON_LD.findall(page or ""):
        try:
            data = json.loads(html_lib.unescape(block))
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph") if isinstance(data, dict) else None
        if nodes is None:
            nodes = [data] if isinstance(data, dict) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            headline = str(node.get("headline") or node.get("name") or "").strip()
            desc = str(node.get("description") or "").strip()
            author = node.get("author")
            if isinstance(author, dict):
                author = str(author.get("name") or "").strip()
            elif isinstance(author, list) and author and isinstance(author[0], dict):
                author = str(author[0].get("name") or "").strip()
            else:
                author = str(author or "").strip()
            if headline and "title" not in out:
                out["title"] = headline
            if desc and "caption" not in out:
                out["caption"] = desc
            if author and "author" not in out:
                out["author"] = author
    return out


def oembed_href(page: str) -> str:
    for tag in OEMBED_LINK.findall(page or ""):
        attrs = _attrs(tag)
        href = attrs.get("href") or ""
        kind = (attrs.get("type") or "").lower()
        if href and "json" in kind:
            return html_lib.unescape(href)
    return ""


def _first(meta: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (meta.get(key) or "").strip()
        if value:
            return value
    return ""


def host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")


def guess_media_type(url: str, meta: dict[str, str]) -> str:
    host = host_of(url)
    path = urllib.parse.urlsplit(url).path.lower()
    og_type = (_first(meta, "og:type") or "").lower()
    if any(part in path for part in ("/reel/", "/reels/", "/tiktok.com", "/shorts/")):
        return "Vídeo"
    if host.endswith("tiktok.com"):
        return "Vídeo"
    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com") or host == "youtu.be":
        return "Vídeo"
    if "video" in og_type:
        return "Vídeo"
    if host:
        return "Link"
    return "Ideia"


def split_instagram(meta: dict[str, str]) -> tuple[str, str, str]:
    """Return (title, caption, author) from Instagram OG/twitter tags."""
    twitter = _first(meta, "twitter:title")
    og_title = _first(meta, "og:title")
    desc = _first(meta, "og:description", "description")
    author = ""
    caption = ""
    title = twitter or og_title

    tw = TWITTER_AUTHOR.search(twitter)
    if tw:
        author = tw.group(2).strip()
        title = f"{tw.group(1).strip()} (@{author})"

    ig = INSTAGRAM_DESC.match(desc)
    if ig:
        author = author or ig.group(1).strip()
        caption = ig.group(2).strip().strip('"')
    else:
        named = IG_TITLE_AUTHOR.match(og_title)
        if named:
            title = title or named.group(1).strip()
            caption = named.group(2).strip().strip('"')
        else:
            caption = desc

    if not caption:
        caption = desc
    if author and author not in title:
        title = f"{title} (@{author})" if title else f"@{author}"
    return title.strip(), caption.strip(), author.strip()


def fetch(url: str, accept: str = "text/html") -> tuple[int, str]:
    last_error = ""
    last_body = ""
    last_status = 0
    for agent in USER_AGENTS:
        req = urllib.request.Request(
            url,
            headers={**HEADERS_BASE, "User-Agent": agent, "Accept": accept},
        )
        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read(400_000).decode(charset, "replace")
                status = resp.status
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            last_status = exc.code
            try:
                last_body = exc.read(800).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                last_body = ""
            continue
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = str(exc)
            continue
        if accept.startswith("application/json"):
            return status, body
        meta = parse_meta(body)
        if _first(meta, "og:title", "twitter:title", "og:description", "description", "title"):
            return status, body
        last_status, last_body = status, body
    if last_body:
        return last_status, last_body
    return last_status, last_error


def oembed(url: str, page: str = "") -> dict[str, str]:
    host = host_of(url)
    endpoints = []
    discovered = oembed_href(page)
    if discovered:
        endpoints.append(discovered)
    if host.endswith("tiktok.com"):
        endpoints.append("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(url, safe=""))
    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com") or host == "youtu.be":
        endpoints.append("https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe=""))
    out: dict[str, str] = {}
    seen: set[str] = set()
    for endpoint in endpoints:
        if endpoint in seen:
            continue
        seen.add(endpoint)
        status, body = fetch(endpoint, accept="application/json")
        if status != 200:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        out["title"] = str(data.get("title") or "").strip()
        out["author"] = str(data.get("author_name") or "").strip()
        out["image"] = str(data.get("thumbnail_url") or "").strip()
        if out.get("title") or out.get("author"):
            break
    return {k: v for k, v in out.items() if v}


def preview(url: str) -> dict[str, Any]:
    source = canonical_url(url)
    empty = {
        "ok": False,
        "url": source or url,
        "canonical": source or url,
        "title": "",
        "caption": "",
        "author": "",
        "site": "",
        "image": "",
        "media_type": "Link" if source else "Ideia",
        "evidence": "none",
        "error": "empty url" if not source else "",
    }
    if not source.startswith("http"):
        empty["error"] = "not an http(s) url"
        return empty
    status, body = fetch(source)
    meta = parse_meta(body) if status and "<" in (body or "") else {}
    ld = parse_json_ld(body) if status and "<" in (body or "") else {}
    extra = oembed(source, body if status else "")
    title = extra.get("title") or ld.get("title") or ""
    caption = ld.get("caption") or ""
    author = extra.get("author") or ld.get("author") or ""
    image = extra.get("image") or _first(meta, "og:image", "twitter:image")
    site = _first(meta, "og:site_name") or host_of(source)

    if host_of(source).endswith("instagram.com"):
        ig_title, ig_caption, ig_author = split_instagram(meta)
        title = title or ig_title
        caption = caption or ig_caption
        author = author or ig_author
    else:
        title = title or _first(meta, "og:title", "twitter:title", "title")
        caption = caption or _first(meta, "og:description", "description", "twitter:description")
        author = author or _first(meta, "author", "article:author")

    canonical = _first(meta, "og:url") or source
    media_type = guess_media_type(canonical, meta)
    ok = bool(title or caption)
    return {
        "ok": ok,
        "url": source,
        "canonical": canonical,
        "title": title[:200],
        "caption": caption[:4000],
        "author": author[:120],
        "site": site[:80],
        "image": image[:2000],
        "media_type": media_type,
        "evidence": "caption" if ok else "none",
        "error": "" if ok else (f"no public metadata (HTTP {status})" if status else body[:200]),
    }


def format_content(data: dict[str, Any], owner_note: str = "") -> str:
    lines: list[str] = []
    if owner_note.strip():
        lines.append(owner_note.strip())
        lines.append("")
    if data.get("author"):
        lines.append(f"Author: {data['author']}")
    if data.get("caption"):
        lines.append("Caption (public metadata):")
        lines.append(str(data["caption"]).strip())
    elif data.get("title"):
        lines.append(str(data["title"]).strip())
    evidence = data.get("evidence") or "none"
    if evidence == "caption":
        lines.append("")
        lines.append("Evidence: public caption/title only — video not watched, audio not transcribed.")
    elif evidence == "none":
        lines.append("")
        lines.append("Evidence: none — public page returned no caption. Saved the URL as sent.")
    return "\n".join(lines).strip()


def apply_to_capture(args: Any, data: dict[str, Any]) -> Any:
    """Fill empty capture fields from a preview. Existing title/content win."""
    source = data.get("canonical") or data.get("url") or ""
    if source and not (getattr(args, "source", None) or getattr(args, "url", None)):
        args.source = source
        args.url = source
    if not (getattr(args, "title", None) or "").strip():
        args.title = (data.get("title") or data.get("caption") or source or "untitled")[:180]
    if not (getattr(args, "content", None) or "").strip() and not getattr(args, "content_file", None):
        args.content = format_content(data)
    if getattr(args, "type", None) in (None, "", "Ideia") and data.get("media_type") in ("Link", "Vídeo"):
        args.type = data["media_type"]
    return args


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("usage: preview_link.py <url>", file=sys.stderr)
        return 2
    result = preview(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
