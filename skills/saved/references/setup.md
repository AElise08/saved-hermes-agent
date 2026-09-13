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
on the phone. **Never ask them to paste the token into chat.** Point them
at the host `.env` + `compose.override.yml` flow in the README.

## 1. Notion token (host, not chat)

They create an internal integration at https://www.notion.so/my-integrations.

On the machine running Docker:

```sh
cp .env.example .env
chmod 600 .env
# put NOTION_API_KEY in .env
cp compose.override.example.yml compose.override.yml
# uncomment NOTION_API_KEY
docker compose up -d --force-recreate
```

Never echo the token, never put it in memory, never paste it back after
setup. If they already pasted it in chat, save it to `.env`, confirm without
repeating it, and tell them to rotate it.

## 2. Share THEIR database, then one command

They pick (or create) a database they own. In Notion: database `...` →
**Connections** → add the integration. Send Saved the **database** URL
(not a regular page).

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-from-url "<their-database-url>"
python3 /var/lib/hermes/scripts/notion_ideas.py doctor
```

`setup-from-url` extracts the database id, resolves `data_sources[0].id`,
creates missing Saved properties, and writes `notion-ideas.json`. Placeholders
(`REPLACE_WITH_YOUR_...`) mean setup is not done.

Required properties: `Name` (title), `Conteúdo` (rich_text), `Status` (select:
Inbox, Explorar, Em andamento, Concluída, Arquivada), `Tipo` (select: Ideia,
Link, Texto, Imagem, PDF, Vídeo), `Temas` (multi-select), `Fonte` (url),
`Capturado em` (date), `Próxima ação` (rich_text).

## 3. Timezone and weekly hour

Ask where they are. Write an IANA zone to `saved-settings.json` (`timezone`).
That file wins over container `TZ`. Optionally `weekly_hour` / `locale`
(`en` or `pt`). Do not assume a country.

## 4. How to use it (tell them, once setup works)

In their language, something like:

- Send anything — a link, a voice note, a screenshot, a half-formed idea.
  Saved archives it in *your* Notion.
- If it is not for this week, say so. Saved remembers and keeps it out of
  the weekly three.
- Once a week, Saved texts three ideas you can actually explore now — not
  the whole archive.
