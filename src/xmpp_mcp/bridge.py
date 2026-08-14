from __future__ import annotations

import asyncio
import hashlib
import ssl
import uuid
from datetime import UTC, datetime
from typing import Any

import slixmpp

from xmpp_mcp.config import Settings, bare_jid
from xmpp_mcp.store import MessageStore

CHAT_STATES = frozenset({"active", "composing", "gone", "inactive", "paused"})
WAITING_STATUS = "Ожидаю указания"
WORKING_STATUS = "Работаю"


class RestrictedXmppClient(slixmpp.ClientXMPP):
    def __init__(self, settings: Settings, store: MessageStore, changed: asyncio.Condition):
        super().__init__(settings.login, settings.password)
        self.settings = settings
        self.store = store
        self.changed = changed
        self.ready = asyncio.Event()
        self.last_error: str | None = None
        self.ssl_context = ssl.create_default_context()

        self.add_event_handler("session_start", self._session_start)
        self.add_event_handler("message", self._message)
        self.add_event_handler("disconnected", self._disconnected)
        self.add_event_handler("connection_failed", self._connection_failed)
        self.register_plugin("xep_0030")
        self.register_plugin("xep_0085")
        self.register_plugin("xep_0198")
        self.register_plugin("xep_0199")
        self.register_plugin("xep_0203")
        self.register_plugin("xep_0359")

    async def _session_start(self, _event: Any) -> None:
        self.send_presence()
        self.ready.set()
        self.last_error = None

    def _disconnected(self, _event: Any) -> None:
        self.ready.clear()

    def _connection_failed(self, event: Any) -> None:
        self.ready.clear()
        self.last_error = str(event)

    async def _message(self, message: Any) -> None:
        sender = bare_jid(str(message["from"]))
        if sender != self.settings.allowed_jid:
            return
        if str(message["type"]) not in {"chat", "normal"}:
            return
        body = str(message["body"]).strip()
        if not body:
            return

        thread_id = str(message["thread"]).strip() or None
        stanza_id = str(message["id"]).strip()
        delayed_at = str(message["delay"]["stamp"] or "")
        if not stanza_id:
            stable = f"{sender}\0{body}\0{thread_id or ''}\0{delayed_at}"
            stanza_id = hashlib.sha256(stable.encode()).hexdigest()
        received_at = delayed_at or datetime.now(UTC).isoformat()
        cursor = self.store.add(
            message_id=stanza_id,
            sender=sender,
            body=body,
            thread_id=thread_id,
            received_at=received_at,
        )
        if cursor is not None:
            async with self.changed:
                self.changed.notify_all()


class XmppBridge:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = MessageStore(settings.state_dir / "messages.sqlite3")
        self.changed = asyncio.Condition()
        self.client = RestrictedXmppClient(settings, self.store, self.changed)
        self._connect_lock = asyncio.Lock()

    async def ensure_connected(self) -> None:
        if self.client.ready.is_set():
            return
        async with self._connect_lock:
            if self.client.ready.is_set():
                return
            self.client.connect(self.settings.host, self.settings.port)
            await asyncio.wait_for(
                self.client.ready.wait(), timeout=self.settings.connect_timeout
            )

    async def send(self, text: str, request_id: str | None = None) -> dict[str, str]:
        text = text.strip()
        if not text:
            raise ValueError("text must not be empty")
        await self.ensure_connected()
        request_id = request_id or str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        message = self.client.make_message(
            mto=self.settings.allowed_jid,
            mbody=text,
            mtype="chat",
        )
        message["id"] = message_id
        message["thread"] = request_id
        message.send()
        self._publish_presence(WAITING_STATUS)
        return {
            "message_id": message_id,
            "request_id": request_id,
            "recipient": self.settings.allowed_jid,
        }

    async def set_chat_state(
        self, state: str, request_id: str | None = None
    ) -> dict[str, str]:
        state = state.strip().lower()
        if state not in CHAT_STATES:
            allowed = ", ".join(sorted(CHAT_STATES))
            raise ValueError(f"state must be one of: {allowed}")
        await self.ensure_connected()
        message = self.client.make_message(
            mto=self.settings.allowed_jid,
            mtype="chat",
        )
        message["chat_state"] = state
        if request_id:
            message["thread"] = request_id
        message.send()
        result = {
            "state": state,
            "recipient": self.settings.allowed_jid,
        }
        if request_id:
            result["request_id"] = request_id
        return result

    def _publish_presence(self, status: str) -> None:
        self.client.send_presence(pstatus=status)

    def poll(
        self, after_cursor: int, limit: int = 20, request_id: str | None = None
    ) -> dict[str, Any]:
        messages = self.store.after(
            after_cursor, limit=limit, thread_id=request_id
        )
        next_cursor = messages[-1].cursor if messages else max(
            after_cursor, self.store.latest_cursor() if request_id is None else after_cursor
        )
        return {
            "messages": [message.as_dict() for message in messages],
            "next_cursor": next_cursor,
        }

    async def wait(
        self,
        after_cursor: int,
        timeout_seconds: float = 300,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        await self.ensure_connected()
        self._publish_presence(WAITING_STATUS)
        existing = self.poll(after_cursor, request_id=request_id)
        if existing["messages"]:
            self._publish_presence(WORKING_STATUS)
            return existing

        timeout_seconds = max(1, min(timeout_seconds, 1800))
        try:
            async with asyncio.timeout(timeout_seconds):
                async with self.changed:
                    while True:
                        await self.changed.wait()
                        result = self.poll(after_cursor, request_id=request_id)
                        if result["messages"]:
                            self._publish_presence(WORKING_STATUS)
                            return result
        except TimeoutError:
            return {"messages": [], "next_cursor": after_cursor, "timed_out": True}

    async def status(self) -> dict[str, Any]:
        try:
            await self.ensure_connected()
        except (OSError, TimeoutError) as error:
            return {
                "connected": False,
                "error": self.client.last_error or str(error),
                "jid": bare_jid(self.settings.login),
                "allowed_jid": self.settings.allowed_jid,
            }
        return {
            "connected": self.client.ready.is_set(),
            "jid": bare_jid(self.settings.login),
            "allowed_jid": self.settings.allowed_jid,
            "latest_cursor": self.store.latest_cursor(),
        }
