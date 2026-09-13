# Weekly idea picks

Use this whenever the owner asks for ideas for the week, what to explore, the
weekly shortlist, or phrases like "ideias da semana", "o que explorar", or
"três ideias".

## Not the same as "what I saved this week"

**Weekly picks** = three ideas to *explore now* (filtered).

**Saved this week** = inventory of recent captures (unfiltered).

If the owner asks for weekly picks / what to explore, do **not** list every
Notion item captured since Monday. That is the wrong answer. Run `weekly-picks`
only.

If they explicitly ask what they *saved* recently ("o que salvei esta semana"),
use `notion_ideas.py search` and filter by capture date — still do not mix that
with weekly picks.

## Hard rule

Never invent picks from memory or conversation. Always run:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py weekly-picks
```

For a scheduled digest, the wrapper is:

```bash
python3 /var/lib/hermes/scripts/weekly_ideas_digest.py
```

## What "explorable this week" means

The owner wants **three ideas they can actually touch during the next 7 days**,
not a bucket list.

Prefer items that have a concrete micro-action (listen, read, test, compare,
verify) in under about two hours total.

Before picking, read owner context from chat memory:

```bash
python3 /var/lib/hermes/scripts/notion_ideas.py context show
```

Exclude or defer (see also `/var/lib/hermes/saved-context.json`):

- topics and facts **this owner** marked as later;
- explicit timing language (`Algum dia`, someday, next year, not this week);
- items already `Concluída`, `Arquivada`, or `Em andamento`;
- repeats chosen in the last two weeks (the script tracks this).

Do not skip travel, weddings, or any other life event unless this owner said
it is later. That list is empty on a fresh install.

Balance the three picks:

1. one **easy** win;
2. one **meaningful** item aligned with current focus (study, work, skills);
3. one **exploratory** but still week-sized.

Saving an idea must not silently turn it into a task. Weekly picks are a
separate layer: suggestions for attention, not obligations.

## Response shape in chat

Reply briefly in the owner's language:

- numbered list of exactly three picks;
- each with title, why it fits **this week**, and the concrete next action;
- Notion link when available;
- one line noting long-term items were filtered out when relevant.

If the script returns fewer than three eligible items, say so honestly and show
what is available instead of padding with unrealistic choices.

## After the owner reacts

- "não agora" / "depois" → do not push; optionally add topic `Algum dia` via
  `notion_ideas.py organize`.
- "essa sim" → update status to `Em andamento` only when the owner confirms.
- "outra" → rerun `weekly-picks` and offer a replacement from the next ranked
  candidate.
