# First-run setup (this owner's vault)

Saved does not ship a shared vault. Every install talks to **the person
texting it**. They choose, on first contact:

1. **Local** — ideas stay in a JSON file on this machine (`/.saved/vault.json`).
   No Notion. Nobody else's database.
2. **Their Notion** — *their* integration and *their* database. Never a sample
   ID and never another person's vault.

Run status first:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-status
```

If `ready` is false, ask which they want, in their language. Do not skip this.
Do not reuse database IDs from a README, a demo, or another person's agent.

## A. Local (no Notion)

If they do not want Notion, or say "save here / on the server / locally":

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-local
python3 /var/lib/hermes/scripts/notion_ideas.py doctor
```

Then capture as usual. Confirm without a Notion link — there isn't one.

## B. Their Notion

**Never ask them to paste the token into chat.** Host `.env` +
`compose.override.yml` (see the README).

They create an internal integration at https://www.notion.so/my-integrations,
share **their** database (`...` → Connections), then send the **database** URL:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-from-url "<their-database-url>"
python3 /var/lib/hermes/scripts/notion_ideas.py doctor
```

Required properties: `Name` (title), `Conteúdo` (rich_text), `Status` (select:
Inbox, Explorar, Em andamento, Concluída, Arquivada), `Tipo` (select: Ideia,
Link, Texto, Imagem, PDF, Vídeo), `Temas` (multi-select), `Fonte` (url),
`Capturado em` (date), `Próxima ação` (rich_text).

## Timezone and weekly hour

Ask where they are. Write an IANA zone to `saved-settings.json` (`timezone`).
That file wins over container `TZ`. Optionally `weekly_hour` / `locale`
(`en` or `pt`). Do not assume a country.

## How to use it (tell them, once setup works)

- Send anything — a link, a voice note, a screenshot, a half-formed idea.
- If it is not for this week, say so.
- Once a week, Saved texts three ideas they can actually explore now.
