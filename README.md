# Saved

Text it anything: a link, a voice note, a screenshot, a half-formed idea.
Saved keeps it in **your** vault — on this machine, or in **your** Notion,
you choose on the first message — and once a week texts **three** ideas you
can actually explore now. Not the whole archive. Not someone else's notebook.

First question, in the language you wrote in:

**Guardar aqui na máquina, ou no Notion?**

## Use cases

- **Capture from chat.** Forward a reel, a link, a screenshot, or a half-formed
  thought. Saved writes it into **your** vault — this machine or your Notion —
  with source, date, and a next action. You do not copy-paste into a database.
- **Three this week.** Once a week it texts three ideas you can actually
  explore now. Not the whole Inbox. What you marked later stays out.
- **Later still counts.** “Not this week”, “algum dia”, “years away”: it stays
  saved and off the shortlist. Saved does not invent a life plan for you.

## Install

You need Git, Docker Compose, and **Python 3.10+** (the helper scripts use
3.10 syntax; the agent itself runs inside Docker).

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/AElise08/saved-hermes-agent.git
cd saved-hermes-agent

plow-agents login                 # text the printed “Plow Activate: …” code
plow-agents lines                 # pick a line whose STATUS is free
plow-agents mint ln_xxx           # writes ./plow-credentials — do this before the first up
docker compose up --build -d
docker compose logs -f agent      # wait for: plow-init: configured ... as cht_
```

If you have no assistant line yet: `plow-agents login --new-line`, then `lines`
and `mint`.

`plow-credentials` and `.env` are gitignored. Do not commit them.

## How to use it

Text the line you minted.

1. **Choose the vault** (first messages). Saved will ask.

   **Local (no Notion):** answer the machine. Saved runs `setup-local`. Ideas
   live in the agent home volume (`/var/lib/hermes/.saved/vault.json`), only
   on that install.

   **Your Notion:** create an internal integration at
   https://www.notion.so/my-integrations and share **your** database with it
   (`...` → Connections). Put the token in a host-side `.env`, never in chat:

   ```sh
   cp .env.example .env
   chmod 600 .env
   # edit .env and set NOTION_API_KEY
   cp compose.override.example.yml compose.override.yml
   # uncomment NOTION_API_KEY in compose.override.yml
   docker compose up -d --force-recreate
   ```

   Recreating the container or running `docker compose down -v` replaces the
   in-container home. Keep the token on the host `.env` so it survives.
   Local vault files live in that volume too — `down -v` wipes them.

   Then send Saved the **database** link (not a regular page). It runs
   `setup-from-url`. Someone else’s IDs will not work and should not be copied.

   Required Notion properties and types: `Name` (title), `Conteúdo` (text),
   `Status` (select), `Tipo` (select), `Temas` (multi-select), `Fonte` (URL),
   `Capturado em` (date), and `Próxima ação` (text). Required Status options:
   Inbox, Explorar, Em andamento, Concluída, Arquivada. Required Tipo options:
   Ideia, Link, Texto, Imagem, PDF, Vídeo. `setup-from-url` adds any of these
   that are missing; it will not rename a title property that already exists
   under another name.

2. **Send anything** — a link, a voice note, a screenshot, a half-formed idea.
   Saved archives it in the vault you chose.
3. **Say when it is later.** “Not this week”, “years away”, “algum dia”. Saved
   keeps it in the vault and out of the weekly three. What counts as later is
   what *you* said, not a baked-in list of life events.
4. **Once a week** (default Sunday 14:00 in your timezone, UTC until you set
   one) Saved texts three ideas you can actually explore now — not the whole
   archive.

Set timezone in `saved-settings.json` (`timezone`, IANA name) or with `TZ` in
`compose.override.yml`. The JSON value wins if both are set. Chat language
follows whatever you type; Saved writes `locale` (`pt` or `en`) from that so
the weekly three match. Optional env `SAVED_LOCALE` overrides the file.

```sh
cp compose.override.example.yml compose.override.yml
# edit TZ if you want the whole container in that zone, then:
docker compose up -d --force-recreate
```

```sh
docker compose down          # stop, keep memory
docker compose down -v       # wipe local memory (new setup)
plow-agents revoke           # retire the line in plow-credentials
```

## Usage reporting

This image reports token usage to the [Agent Index](https://aiworthusing.com/agent-index)
once an hour: day × model counts, nothing else. The listing page (name, repo,
video) is **not** published by this boot — that is a separate step.

`AGENT_ID` defaults to `saved`.

## Tests

```sh
python3 -m unittest discover -s tests -q
```

## License

MIT. See [LICENSE](LICENSE).
