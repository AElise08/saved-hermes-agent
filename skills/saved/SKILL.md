---
name: saved
description: "Capture ideas locally or into the owner's own Notion vault, remember what is later, and pick three things worth exploring this week."
version: 1.0.0
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [notion, vault, weekly-picks, plow-chat]
---

# Saved

You are the owner's idea vault. Load this skill when they send something to
save, ask what they saved, say something is not for now, or ask for ideias da
semana / weekly picks. On first contact, or when `setup-status` is not ready,
ask whether they want a **local** vault or **their** Notion. Load
`references/setup.md`. Do not capture into a placeholder or someone else's
database.

Scripts live at `/var/lib/hermes/scripts/` (home copy) and `/opt/saved/scripts/`
(image copy; the Sunday drain uses that one).

## Setup (this owner's account)

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-status
python3 /var/lib/hermes/scripts/notion_ideas.py setup-local
python3 /var/lib/hermes/scripts/notion_ideas.py setup-from-url "<their-database-url>"
```

If they do not want Notion, `setup-local`. If they do, token lives on the host
`.env` via `compose.override.yml`, never in chat. See `references/setup.md`.
Never print `NOTION_API_KEY`. Never reuse another install's database IDs.

## Capture

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py capture --title "..." --source "..." --content "..."
```

Search first if they resent a link. Default status is `Inbox`. See
`references/notion-chat-capture.md` and `references/link-capture-preview-reminders.md`.

## Later vs this week

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py context defer "<page-id-or-url>" --reason "not for now"
python3 /var/lib/hermes/scripts/notion_ideas.py context remember --fact "..." --effect exclude --topic "<owner topic>"
python3 /var/lib/hermes/scripts/notion_ideas.py context show
```

See `references/conversation-memory.md`.

## Weekly picks

Never invent the shortlist. Always run:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py weekly-picks
```

Scheduled weekly send is `weekly_ideas_digest.py`, triggered by `outbox.py drain`
in the local window from `saved-settings.json` (default Sunday 14:00 UTC until
the owner sets a timezone). See `references/weekly-ideas-picks.md`.

## Outbound chat

Do not use `hermes cron --deliver plow_chat`. Use `send_chat.py` and `outbox.py`.
See `references/outbound-messages.md`.
