# First-run setup (this owner's Notion, not yours)

Saved does not ship a shared vault. Every install talks to **the person
texting it**: their Notion integration, their database, their timezone.

On first contact — and whenever capture fails with `needs_setup` or
`missing_token` — walk them through this. Do not skip it. Do not reuse
database IDs from a README, a demo, or another person's agent.

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-status
```

If `ready` is false, explain the steps below in their language, briefly,
on the phone. Wait for their answers. Then write config. Then `doctor`.

## 1. Notion integration (their account)

They create an internal integration at https://www.notion.so/my-integrations
and copy the token once.

Store it as `NOTION_API_KEY` in `${HERMES_HOME}/.env` (`chmod 600`). Never
echo the token, never put it in memory, never paste it back in chat after
setup. If they pasted it in chat, save it, confirm without repeating it, and
tell them to rotate it.

## 2. Share THEIR database

They pick (or create) a database they own — often named Ideias, but the name
is theirs. In Notion: database `...` → **Connections** → add the integration
they just created.

The URL looks like `notion.so/Name-{database_id}`. The `data_source_id` comes
from `GET /v1/databases/{database_id}` → `data_sources[0].id`. See
`notion-api-access.md`.

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-write \
  --database-id "<their-database-id>" \
  --data-source-id "<their-data-source-id>" \
  --database-name "<their-title>"
python3 /var/lib/hermes/scripts/notion_ideas.py doctor
```

Placeholders (`REPLACE_WITH_YOUR_...`) mean setup is not done.

## 3. Timezone and weekly hour

Ask where they are. Write an IANA zone to `saved-settings.json` (`timezone`)
and optionally `weekly_hour` / `locale` (`en` or `pt`). Do not assume a
country.

## 4. How to use it (tell them, once setup works)

In their language, something like:

- Send anything — a link, a voice note, a screenshot, a half-formed idea.
  Saved archives it in *your* Notion.
- If it is not for this week, say so. Saved remembers and keeps it out of
  the weekly three.
- Once a week, Saved texts three ideas you can actually explore now — not
  the whole archive.

Expected Notion properties (create them if missing; `doctor` reports schema):
`Name`, `Conteúdo` or similar body, `Status`, topics/tags. The scripts are
written for a Portuguese-labelled Ideias schema; map or rename with the
owner if their properties differ — do not silently write to the wrong DB.
