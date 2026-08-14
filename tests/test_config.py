from xmpp_mcp.config import Settings, bare_jid, generated_display_name


def test_bare_jid_removes_resource_and_normalizes() -> None:
    assert bare_jid(" Alice@Example.Org/Phone ") == "alice@example.org"


def test_generated_display_name_uses_short_host_and_directory_name() -> None:
    assert generated_display_name(
        "avi-ix-sq-dev03.example.org",
        "/home/user/Developer/Avito/service-search-l2-storage",
    ) == "service-search-l2-storage@avi-ix-sq-dev03"


def test_settings_from_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_XMPP_HOST", "xmpp.example.org")
    monkeypatch.setenv("MCP_XMPP_LOGIN", "bot@example.org/codex")
    monkeypatch.setenv("MCP_XMPP_PASSWORD", "secret")
    monkeypatch.setenv("MCP_XMPP_ALLOWED_JID", "Owner@Example.org/Phone")
    monkeypatch.setenv("MCP_XMPP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("MCP_XMPP_WORKING_DIR", "/work/my-service")

    settings = Settings.from_env()

    assert settings.host == "xmpp.example.org"
    assert settings.login == "bot@example.org/codex"
    assert settings.password == "secret"
    assert settings.allowed_jid == "owner@example.org"
    assert settings.display_name.startswith("my-service@")
    assert settings.state_dir.stat().st_mode & 0o777 == 0o700
