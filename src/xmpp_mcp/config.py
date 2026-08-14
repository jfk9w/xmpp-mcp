from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def bare_jid(value: str) -> str:
    return value.strip().split("/", 1)[0].casefold()


@dataclass(frozen=True, slots=True)
class Settings:
    login: str
    password: str
    allowed_jid: str
    host: str
    port: int
    connect_timeout: float
    state_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        host = os.environ.get("MCP_XMPP_HOST", "").strip()
        login = os.environ.get("MCP_XMPP_LOGIN", "").strip()
        password = os.environ.get("MCP_XMPP_PASSWORD", "")
        allowed_jid = bare_jid(os.environ.get("MCP_XMPP_ALLOWED_JID", ""))
        if not host:
            raise ValueError("MCP_XMPP_HOST is required")
        if not login or "@" not in bare_jid(login):
            raise ValueError("MCP_XMPP_LOGIN must be a JID")
        if not password:
            raise ValueError("MCP_XMPP_PASSWORD is required")
        if not allowed_jid or "@" not in allowed_jid:
            raise ValueError("MCP_XMPP_ALLOWED_JID must be a bare JID")

        state_dir = Path(
            os.environ.get("MCP_XMPP_STATE_DIR", "~/.local/state/xmpp-mcp")
        ).expanduser()
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        state_dir.chmod(0o700)

        settings = cls(
            login=login,
            password=password,
            allowed_jid=allowed_jid,
            host=host,
            port=int(os.environ.get("MCP_XMPP_PORT", "5222")),
            connect_timeout=float(os.environ.get("MCP_XMPP_CONNECT_TIMEOUT", "20")),
            state_dir=state_dir,
        )
        return settings
