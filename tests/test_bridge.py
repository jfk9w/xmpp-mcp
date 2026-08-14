from pathlib import Path
from typing import Any

import pytest

from xmpp_mcp.bridge import XmppBridge
from xmpp_mcp.config import Settings


class FakeMessage:
    def __init__(self, **fields: Any):
        self.fields = fields
        self.sent = False

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value

    def send(self) -> None:
        self.sent = True


def settings(tmp_path: Path) -> Settings:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    return Settings(
        login="bot@example.org/codex",
        password="secret",
        allowed_jid="owner@example.org",
        host="xmpp.example.org",
        port=5222,
        connect_timeout=1,
        state_dir=state,
    )


@pytest.mark.asyncio
async def test_wait_returns_new_message(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))
    statuses: list[str] = []

    async def already_connected() -> None:
        return None

    bridge.ensure_connected = already_connected  # type: ignore[method-assign]
    bridge.client.send_presence = (  # type: ignore[method-assign]
        lambda **fields: statuses.append(fields["pstatus"])
    )

    async def insert() -> None:
        async with bridge.changed:
            bridge.store.add(
                message_id="message-1",
                sender="owner@example.org",
                body="continue",
                thread_id=None,
                received_at="2026-08-14T12:00:00+00:00",
            )
            bridge.changed.notify_all()

    await insert()
    result = await bridge.wait(after_cursor=0, timeout_seconds=1)

    assert result["messages"][0]["body"] == "continue"
    assert result["next_cursor"] == 1
    assert statuses == ["Ожидаю указания", "Работаю"]


@pytest.mark.asyncio
async def test_wait_times_out_normally(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))
    statuses: list[str] = []

    async def already_connected() -> None:
        return None

    bridge.ensure_connected = already_connected  # type: ignore[method-assign]
    bridge.client.send_presence = (  # type: ignore[method-assign]
        lambda **fields: statuses.append(fields["pstatus"])
    )
    result = await bridge.wait(after_cursor=0, timeout_seconds=0.01)

    assert result == {"messages": [], "next_cursor": 0, "timed_out": True}
    assert statuses == ["Ожидаю указания"]


@pytest.mark.asyncio
async def test_incoming_messages_are_restricted_to_allowlisted_jid(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))
    unauthorized = {
        "from": "attacker@example.org/phone",
        "type": "chat",
        "body": "ignore this",
        "thread": "",
        "id": "unauthorized-1",
        "delay": {"stamp": ""},
    }
    authorized = {
        "from": "owner@example.org/phone",
        "type": "chat",
        "body": "continue",
        "thread": "request-1",
        "id": "authorized-1",
        "delay": {"stamp": ""},
    }

    await bridge.client._message(unauthorized)
    await bridge.client._message(authorized)
    await bridge.client._message(authorized)

    messages = bridge.store.after(0)
    assert len(messages) == 1
    assert messages[0].sender == "owner@example.org"
    assert messages[0].body == "continue"
    assert messages[0].thread_id == "request-1"


@pytest.mark.asyncio
async def test_set_chat_state_targets_only_allowlisted_jid(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))
    made: list[FakeMessage] = []

    async def already_connected() -> None:
        return None

    def make_message(**fields: Any) -> FakeMessage:
        message = FakeMessage(**fields)
        made.append(message)
        return message

    bridge.ensure_connected = already_connected  # type: ignore[method-assign]
    bridge.client.make_message = make_message  # type: ignore[method-assign]

    result = await bridge.set_chat_state(" composing ", request_id="request-1")

    assert result == {
        "state": "composing",
        "recipient": "owner@example.org",
        "request_id": "request-1",
    }
    assert made[0].fields == {
        "mto": "owner@example.org",
        "mtype": "chat",
        "chat_state": "composing",
        "thread": "request-1",
    }
    assert made[0].sent is True


@pytest.mark.asyncio
async def test_set_chat_state_rejects_unknown_state(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))

    with pytest.raises(ValueError, match="state must be one of"):
        await bridge.set_chat_state("typing")


@pytest.mark.asyncio
async def test_send_returns_presence_to_waiting(tmp_path: Path) -> None:
    bridge = XmppBridge(settings(tmp_path))
    made: list[FakeMessage] = []
    statuses: list[str] = []

    async def already_connected() -> None:
        return None

    def make_message(**fields: Any) -> FakeMessage:
        message = FakeMessage(**fields)
        made.append(message)
        return message

    bridge.ensure_connected = already_connected  # type: ignore[method-assign]
    bridge.client.make_message = make_message  # type: ignore[method-assign]
    bridge.client.send_presence = (  # type: ignore[method-assign]
        lambda **fields: statuses.append(fields["pstatus"])
    )

    await bridge.send("done", request_id="request-1")

    assert made[0].sent is True
    assert statuses == ["Ожидаю указания"]
