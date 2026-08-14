# xmpp-mcp

A deliberately small XMPP MCP server for human-in-the-loop notifications.
It connects as a dedicated bot account and communicates with exactly one
allowlisted bare JID.

## Security model

- The recipient is fixed by `MCP_XMPP_ALLOWED_JID`; MCP calls cannot override it.
- Messages from every other JID are discarded before persistence.
- Host, login, and password are supplied through the MCP process environment.
- TLS certificate verification is enabled with the system trust store.
- XEP-0198 stream management is requested when supported by the server.
- Accepted messages are deduplicated and persisted in a mode-`0600` SQLite
  database.
- No shell, file-transfer, roster-management, MUC, or arbitrary-recipient tools
  are exposed.

This protects the messaging boundary, but a reply in XMPP is still an agent
instruction, not a substitute for a Codex approval required by the client.

## Tools

- `xmpp_status`
- `xmpp_send_message`
- `xmpp_poll_messages`
- `xmpp_wait_for_message`

Polling and waiting use durable integer cursors. Save `next_cursor` and pass it
as `after_cursor` on the next call. `request_id` maps to the XMPP thread field;
not every mobile client preserves threads, so cursor order remains the fallback.

## Setup

```bash
cd ~/Developer/xmpp-mcp
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Export configuration before launching the MCP server:

```bash
export MCP_XMPP_HOST='xmpp.example.org'
export MCP_XMPP_LOGIN='codex-bot@example.org/codex'
export MCP_XMPP_PASSWORD='BOT_ACCOUNT_PASSWORD'
export MCP_XMPP_ALLOWED_JID='you@example.org'
```

Optional variables such as `MCP_XMPP_PORT`, `MCP_XMPP_CONNECT_TIMEOUT`, and
`MCP_XMPP_STATE_DIR` are documented in `.env.example`.

Run directly:

```bash
.venv/bin/xmpp-mcp
```

## Codex configuration

Add a stdio MCP server to `~/.codex/config.toml`:

```toml
[mcp_servers.xmpp]
command = "/home/user/Developer/xmpp-mcp/.venv/bin/xmpp-mcp"

[mcp_servers.xmpp.env]
MCP_XMPP_HOST = "xmpp.example.org"
MCP_XMPP_LOGIN = "codex-bot@example.org/codex"
MCP_XMPP_PASSWORD = "BOT_ACCOUNT_PASSWORD"
MCP_XMPP_ALLOWED_JID = "you@example.org"
```

Restart the Codex session after changing MCP configuration.

## Checks

```bash
.venv/bin/ruff check .
.venv/bin/pytest
```
