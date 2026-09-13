# Notion API access: authentication vs page authorization

Use this reference when a Notion integration token is available but a page or
database is not visible through the API.

## Safe setup

1. Store the token as `NOTION_API_KEY` in `${HERMES_HOME:-~/.hermes}/.env`.
2. Restrict the file: `chmod 600 ${HERMES_HOME:-~/.hermes}/.env`.
3. Never print the token, include it in a report, save it to memory, or paste it
   into a generated command.
4. Use `Notion-Version: 2025-09-03` on HTTP requests.

If the owner explicitly supplied the token for setup, consume it without
repeating it and return only sanitized response fields. Once the setup is
verified, recommend rotating a token that was pasted into chat, then replace
it in the local environment file and rerun the identity probe; do not leave the
old value in reports, memory, examples, or generated commands.

## Read-only verification sequence

First verify the credential itself:

```sh
curl -sS https://api.notion.com/v1/users/me \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H 'Notion-Version: 2025-09-03'
```

A successful `object: user` / `type: bot` response means authentication works;
it does not prove access to a particular page.

Then request the known page or data source metadata. If it returns 404 while
`users/me` succeeds, diagnose missing page sharing before rotating the token,
creating a duplicate, or blaming the API.

For Notion's current web UI, the target page/database's top-right `...`
menu may show **Connections** rather than `Connect to`. That submenu can contain
both marketplace connectors and owner-created internal integrations. Select
the internal integration listed under the owner's created integrations, then
confirm the follow-up dialog with **Add to page**. The older `Connect to` label
is equivalent where it is still shown. Do not type an integration display name
into the Share email field or invite a guessed contact address; verify that the
entry is the integration connection first. Reopen the menu and check that the
connection name is no longer `None`, then repeat the metadata request and run a
small read-only query. Only after both work should the automation create or
update pages.

Notion's current API exposes two IDs for a database: the database ID is used
for database metadata and for creating child pages, while the
`data_sources[0].id` returned by `GET /v1/databases/{database_id}` is used to
retrieve the schema and query rows. For a new full-page database, a reliable
sequence is: authorize the page in the UI, `GET /v1/databases/{database_id}`,
`GET /v1/data_sources/{data_source_id}`, patch the database title through
`PATCH /v1/databases/{database_id}`, patch schema properties through
`PATCH /v1/data_sources/{data_source_id}`, and finish with an empty read-only
query. Do not create a test row merely to prove the query works.

## Evidence and reporting

Record the real HTTP status and a redacted error code/message. Do not expose
Authorization headers or response fields that contain secrets. Distinguish:

- invalid/revoked token: identity probe fails;
- valid token, inaccessible resource: identity probe succeeds but page/data
  source returns 404;
- authorized resource: metadata succeeds and exposes the page/data-source ID;
- browser-only operation: use the approved browser as a fallback, and verify a
  fresh session instead of assuming a previous login persisted.

Keep the API path headless for recurring work; reserve browser login for the
one-time connection step and UI capabilities not provided by the API.
