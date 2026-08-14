from pathlib import Path

from xmpp_mcp.store import MessageStore


def add(store: MessageStore, message_id: str, body: str, thread_id: str | None = None):
    return store.add(
        message_id=message_id,
        sender="owner@example.org",
        body=body,
        thread_id=thread_id,
        received_at="2026-08-14T12:00:00+00:00",
    )


def test_store_deduplicates_and_advances_cursor(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "messages.sqlite3")
    first = add(store, "one", "yes")
    duplicate = add(store, "one", "yes")
    second = add(store, "two", "no")

    assert first == 1
    assert duplicate is None
    assert second is not None and second > first
    assert [item.body for item in store.after(0)] == ["yes", "no"]
    assert [item.body for item in store.after(1)] == ["no"]
    assert store.latest_cursor() == second
    assert (tmp_path / "messages.sqlite3").stat().st_mode & 0o777 == 0o600


def test_store_filters_by_request_id(tmp_path: Path) -> None:
    store = MessageStore(tmp_path / "messages.sqlite3")
    add(store, "one", "first", "request-a")
    add(store, "two", "second", "request-b")

    messages = store.after(0, thread_id="request-b")

    assert [message.body for message in messages] == ["second"]
