# Conversation memory for Saved

The owner expects the agent to **learn from chat** — not from a baked-in
biography. What is later for one person (a wedding, a move, a trip) is this
week for another. Persist what *this* owner says, and use that.

## Always persist — do not rely on chat history alone

Chat history is long and may be compacted. After the owner states a durable
fact or deferral, write it to **both**:

1. `saved-context.json` via the helper script (structured; weekly picks read this)
2. Hermes `memory` tool (one short line in MEMORY.md for all sessions)

## Triggers and actions

| Owner says (examples) | Do this |
|-----------------------|---------|
| "não é pra agora", "depois", "anos", "longo prazo", "not for now" about an idea | `context defer` on that Notion item + confirm briefly |
| "X is years away", "that's next year", "not until I move" | `context remember --effect exclude` with the topic/keywords they used |
| "I'm focusing on Y this month" | `context remember --effect note` + memory line |
| "ideias da semana" / "what should I explore" | `weekly-picks` (uses saved-context automatically) |
| "me lembra às 17h", "send this later", "Saturday" | **never** `hermes cron --deliver plow_chat`. Queue with `outbox.py add --at` in *their* timezone |
| "I live in …" / a timezone | write `timezone` in `saved-settings.json` (IANA name). Do not assume a country |
| First sentence in Portuguese or English | `python3 /var/lib/hermes/scripts/saved_config.py set-locale pt` or `en`. Chat has no detector; weekly digest reads this file |

### Defer one idea (not for now)

When the owner rejects an idea for the current week or says to save it for later:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py context defer "<notion-page-id-or-url>" \
  --reason "owner asked to leave it for later"
```

This updates Notion (`Explorar`, topic `Algum dia` when that exists) and
records the item so weekly picks skip it.

### Remember a life fact

Use the owner's own words and topics — do not copy another person's wedding,
trip, or city into the template:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py context remember \
  --fact "<what they said, in one sentence>" \
  --effect exclude --topic "<their topic>" --keyword "<their keyword>"
```

Effects:

- `exclude` — matching topics/keywords leave the weekly shortlist
- `note` — context for replies; does not alone remove items unless keywords match

### Read context before weekly picks or personal advice

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py context show
```

## Memory tool line (after script succeeds)

Append one short §-separated line via the `memory` tool, quoting the owner's
fact, e.g. `Owner: <plan> is not for this week — skip weekly picks.`

Keep each line under one sentence. Do not store secrets. Do not invent
plans they did not state.

## What not to do

- Do not answer weekly picks from memory without running `weekly-picks`.
- Do not assume the owner still wants something they said was "not for now".
- Do not ask them to repeat timeline facts already stored in `context show`.
- Do not assume Brazil, a wedding, or a destination. Ask or read settings.
