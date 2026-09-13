# Saved

Send anything in chat. It archives to **your** Notion vault, remembers what is
later, and every week texts three ideas you can actually explore now.

This is not a shared notebook. Each install talks to that owner's Notion
account, timezone, and “not for now” list. The image ships placeholders. The
agent’s first job is to tell you how to connect yours.

## Install

You need Git, Docker Compose, and Python 3.

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

`plow-credentials` is gitignored. Do not commit it.

## How to use it

Text the line you minted.

1. **Connect your Notion** (first messages). Saved will ask. Create an
   internal integration at https://www.notion.so/my-integrations, share **your**
   database with it, put `NOTION_API_KEY` in the container’s
   `/var/lib/hermes/.env`, and send Saved the database link. It writes
   `notion-ideas.json` for this install only. Someone else’s IDs will not work
   and should not be copied.
2. **Send anything** — a link, a voice note, a screenshot, a half-formed idea.
   Saved archives it in that database.
3. **Say when it is later.** “Not this week”, “years away”, “algum dia”. Saved
   keeps it in the vault and out of the weekly three. What counts as later is
   what *you* said, not a baked-in list of life events.
4. **Once a week** (default Sunday 14:00 in your timezone, UTC until you set
   one) Saved texts three ideas you can actually explore now — not the whole
   archive.

Set timezone with `TZ` in `compose.override.yml` (IANA name, e.g.
`Europe/Lisbon`) or ask Saved in chat. Optional `locale` in
`saved-settings.json`: `en` or `pt`.

```sh
cp compose.override.example.yml compose.override.yml
# edit TZ, then:
docker compose up -d
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

## License

MIT. See [LICENSE](LICENSE).
