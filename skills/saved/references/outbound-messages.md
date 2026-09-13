# Outbound messages (now vs later)

Plow Chat `--deliver` and `hermes send --to plow_chat` **do not work** from
cron or any process outside the live gateway adapter. Never schedule:

```text
hermes cron create ... --deliver plow_chat:...
```

That job can succeed and still never text the owner.

## Send now

```bash
python3 /var/lib/hermes/scripts/send_chat.py "mensagem"
```

## Send later (the owner said "depois", "às 17h", "sábado")

Queue in the owner's timezone (`TZ` or `saved-settings.json`, default UTC). A drain job runs every 5 minutes.

```bash
python3 /var/lib/hermes/scripts/outbox.py add \
  --at "2026-09-13T17:00:00" \
  --reason "lembrete pedido pelo owner" \
  --text "mensagem"
```

`--at now` (or omit) sends immediately.

```bash
python3 /var/lib/hermes/scripts/outbox.py show
```

## Weekly ideas

Weekly send uses `saved-settings.json`: timezone (or `TZ`), weekday (default
Sunday), hour (default 14:00 local). Hermes cron matches in UTC, so do not rely
on `hermes cron` for this. The image runs `outbox.py drain` every 5 minutes;
drain itself sends the digest in that local window. Do not wrap it with
`--deliver`.

## Decide now vs later

If the owner says an idea is not for this week: `context defer` (vault) — do
not text a reminder.

If they want a ping at a clock time: `outbox.py add --at`. Confirm the local
time you queued. Do not create a Hermes cron with plow_chat delivery.
