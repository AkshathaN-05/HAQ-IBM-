"""SQLite access and a small, ordered migration runner."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def run_migrations(db_path: Path) -> list[str]:
    """Apply every migrations/NNN_*.sql file not yet recorded. Returns applied names."""
    conn = connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        applied: list[str] = []
        for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.execute("BEGIN")
            try:
                # executescript commits implicitly, so run statements one by one inside our transaction.
                for statement in _split_sql(sql):
                    conn.execute(statement)
                conn.execute("INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)", (path.name, now_iso()))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            applied.append(path.name)
        return applied
    finally:
        conn.close()


def _split_sql(sql: str) -> list[str]:
    """Split a migration into statements, keeping CREATE TRIGGER ... END; blocks intact."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    statements, buf = [], []
    in_trigger = False
    for line in lines:
        buf.append(line)
        upper = line.strip().upper()
        if upper.startswith("CREATE TRIGGER"):
            in_trigger = True
        joined = "\n".join(buf).strip()
        if in_trigger:
            if upper.endswith("END;"):
                statements.append(joined)
                buf, in_trigger = [], False
        elif joined.endswith(";"):
            statements.append(joined)
            buf = []
    if "\n".join(buf).strip():
        statements.append("\n".join(buf).strip())
    return [s for s in statements if s.strip(" ;\n")]


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def ping(self) -> bool:
        try:
            with self.connection() as c:
                c.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None
