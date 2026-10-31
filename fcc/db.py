"""SQLite connection helpers and the ``.sql`` script executor."""

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def _title_case(value: str | None) -> str | None:
    """Python's ``str.title()`` as a SQL function; NULL stays NULL."""
    return None if value is None else value.title()


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the database, creating the file and its folder if needed.

    The connection is in autocommit mode: use :func:`transaction` to group
    statements. A ``title_case()`` SQL function is registered for the
    ``clean = "title"`` rule.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    # Without this, renaming a table fails while a view still points at the dropped
    # table of the same name, which is exactly the state during a table swap.
    conn.execute('PRAGMA legacy_alter_table = ON')
    conn.create_function('title_case', 1, _title_case, deterministic=True)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Run the enclosed statements atomically; roll back if anything raises."""
    conn.execute('BEGIN')
    try:
        yield
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    conn.execute('COMMIT')


def split_statements(script: str) -> list[str]:
    """Split a SQL script into statements.

    Splits on semicolons that end a complete statement, so a ``;`` inside a
    string, comment or trigger body doesn't break it. Trailing text with no
    statement in it (e.g. a closing comment) is dropped.
    """
    statements, buffer = [], ''
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ''
    leftover = '\n'.join(
        line for line in buffer.splitlines() if line.strip() and not line.strip().startswith('--')
    )
    if leftover:
        statements.append(buffer.strip())
    return statements


def run_sql_file(conn: sqlite3.Connection, path: Path, params: Mapping[str, Any] | None = None) -> None:
    """Execute every statement in a ``.sql`` file inside a single transaction.

    Args:
        conn: Open connection.
        path: The script.
        params: Values for ``:name`` placeholders in the script.
    """
    statements = split_statements(path.read_text(encoding='utf-8'))
    with transaction(conn):
        for statement in statements:
            conn.execute(statement, params or {})


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Whether a table with this name exists."""
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None
