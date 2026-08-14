from xmpp_mcp.config import Settings, bare_jid


def test_bare_jid_removes_resource_and_normalizes() -> None:
    assert bare_jid(" Alice@Example.Org/Phone ") == "alice@example.org"


def test_settings_from_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_XMPP_HOST", "xmpp.example.org")
    monkeypatch.setenv("MCP_XMPP_LOGIN", "bot@example.org/codex")
    monkeypatch.setenv("MCP_XMPP_PASSWORD", "secret")
    monkeypatch.setenv("MCP_XMPP_ALLOWED_JID", "Owner@Example.org/Phone")
    monkeypatch.setenv("MCP_XMPP_STATE_DIR", str(tmp_path / "state"))

    settings = Settings.from_env()

    assert settings.host == "xmpp.example.org"
    assert settings.login == "bot@example.org/codex"
    assert settings.password == "secret"
    assert settings.allowed_jid == "owner@example.org"
    assert settings.state_dir.stat().st_mode & 0o777 == 0o700
