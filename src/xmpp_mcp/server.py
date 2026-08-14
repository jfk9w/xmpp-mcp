from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from xmpp_mcp.bridge import XmppBridge
from xmpp_mcp.config import Settings

mcp = FastMCP("xmpp-mcp")
_bridge: XmppBridge | None = None


def bridge() -> XmppBridge:
    global _bridge
    if _bridge is None:
        _bridge = XmppBridge(Settings.from_env())
    return _bridge


def encoded(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


@mcp.tool()
async def xmpp_status() -> str:
    """Check the restricted XMPP connection and current durable message cursor."""
    return encoded(await bridge().status())


@mcp.tool()
async def xmpp_send_message(text: str, request_id: str | None = None) -> str:
    """Send text to the single configured allowlisted JID.

    The recipient cannot be overridden. Reuse request_id to correlate a response
    when the recipient's XMPP client preserves message threads.
    """
    return encoded(await bridge().send(text=text, request_id=request_id))


@mcp.tool()
async def xmpp_set_chat_state(state: str, request_id: str | None = None) -> str:
    """Publish an XEP-0085 chat state to the single allowlisted JID.

    state must be active, composing, paused, inactive, or gone. The recipient
    cannot be overridden. Pass request_id when the peer preserves XMPP threads.
    """
    return encoded(await bridge().set_chat_state(state=state, request_id=request_id))


@mcp.tool()
def xmpp_poll_messages(
    after_cursor: int = 0,
    limit: int = 20,
    request_id: str | None = None,
) -> str:
    """Read allowlisted messages after a durable cursor without blocking."""
    return encoded(
        bridge().poll(
            after_cursor=max(0, after_cursor),
            limit=limit,
            request_id=request_id,
        )
    )


@mcp.tool()
async def xmpp_wait_for_message(
    after_cursor: int,
    timeout_seconds: float = 300,
    request_id: str | None = None,
) -> str:
    """Wait for the next allowlisted message after a durable cursor.

    timeout_seconds is clamped to 1..1800 seconds. A timeout is a normal result.
    """
    return encoded(
        await bridge().wait(
            after_cursor=max(0, after_cursor),
            timeout_seconds=timeout_seconds,
            request_id=request_id,
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
