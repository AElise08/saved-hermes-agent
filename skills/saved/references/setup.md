# First-run setup (this owner's vault)

Saved does not ship a shared vault. Every install talks to **the person
texting it**. They choose, on first contact.

Run status first:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py setup-status
```

If `ready` is false, ask **exactly this**, then wait. Pick from **this
message's text**, not from the system prompt language:

- They wrote Portuguese: `Guardar aqui na máquina, ou no Notion?`
- They wrote English: `Save here on this machine, or in Notion?`
- No words yet (link / screenshot / voice): both in one line
  `Guardar aqui na máquina, ou no Notion? / Save here on this machine, or in Notion?`

One line. Do not add a tutorial. Do not mention tokens, databases, or anyone
else's Notion in that message. Do not skip this. Do not reuse database IDs
from a README, a demo, or another person's agent.

The first time they write a sentence, save the language so Sunday's three
picks match chat:

```bash
python3 /var/lib/hermes/scripts/saved_config.py set-locale pt
```

or `set-locale en`. There is no detector — you infer from the words they
typed. Do not guess from timezone.

After they answer:

1. **Máquina / here / local** — ideas stay in a JSON file on this machine
   (`/.saved/vault.json`). No Notion.
2. **Notion** — *their* integration and *their* database. Never a sample ID
   and never another person's vault.

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
That file wins over container `TZ`. Optionally `weekly_hour`. Locale is `pt`
or `en` via `saved_config.py set-locale` from the language they write in.
Do not assume a country.

## How to use it (tell them, once setup works)

- Send anything — a link, a voice note, a screenshot, a half-formed idea.
- If it is not for this week, say so.
- Once a week, Saved texts three ideas they can actually explore now.
