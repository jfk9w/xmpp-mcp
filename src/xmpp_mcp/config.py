from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


def bare_jid(value: str) -> str:
    return value.strip().split("/", 1)[0].casefold()


def generated_display_name(hostname: str, working_dir: str) -> str:
    host = hostname.strip().split(".", 1)[0] or "unknown-host"
    path = Path(working_dir).expanduser()
    project = path.name or path.parent.name or "workspace"
    return f"{project[:64]}@{host[:32]}"


@dataclass(frozen=True, slots=True)
class Settings:
    login: str
    password: str
    allowed_jid: str
    host: str
    port: int
    connect_timeout: float
    state_dir: Path
    display_name: str

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
        display_name = generated_display_name(
            socket.gethostname(),
            os.environ.get("MCP_XMPP_WORKING_DIR", os.getcwd()),
        )

        settings = cls(
            login=login,
            password=password,
            allowed_jid=allowed_jid,
            host=host,
            port=int(os.environ.get("MCP_XMPP_PORT", "5222")),
            connect_timeout=float(os.environ.get("MCP_XMPP_CONNECT_TIMEOUT", "20")),
            state_dir=state_dir,
            display_name=display_name,
        )
        return settings
