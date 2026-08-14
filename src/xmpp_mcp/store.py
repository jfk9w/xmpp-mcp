from __future__ import annotations

import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StoredMessage:
    cursor: int
    message_id: str
    sender: str
    body: str
    thread_id: str | None
    received_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MessageStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL UNIQUE,
                sender TEXT NOT NULL,
                body TEXT NOT NULL,
                thread_id TEXT,
                received_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        path.chmod(0o600)

    def add(
        self,
        *,
        message_id: str,
        sender: str,
        body: str,
        thread_id: str | None,
        received_at: str,
    ) -> int | None:
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO messages
                    (message_id, sender, body, thread_id, received_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, sender, body, thread_id, received_at),
            )
            self._connection.commit()
            return int(cursor.lastrowid) if cursor.rowcount else None

    def after(
        self,
        cursor: int,
        *,
        limit: int = 20,
        thread_id: str | None = None,
    ) -> list[StoredMessage]:
        limit = max(1, min(limit, 100))
        query = "SELECT * FROM messages WHERE cursor > ?"
        parameters: list[object] = [max(0, cursor)]
        if thread_id is not None:
            query += " AND thread_id = ?"
            parameters.append(thread_id)
        query += " ORDER BY cursor ASC LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [StoredMessage(**dict(row)) for row in rows]

    def latest_cursor(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COALESCE(MAX(cursor), 0) AS cursor FROM messages"
            ).fetchone()
        return int(row["cursor"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()

