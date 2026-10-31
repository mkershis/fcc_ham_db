"""Discovers and runs the ``.sql`` scripts in the ``sql/<layer>/`` directories."""

import sqlite3
from collections.abc import Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from .db import run_sql_file, split_statements


def discover_scripts(sql_dir: Path, layer: str, patterns: list[str] | None = None) -> list[Path]:
    """List a folder's ``.sql`` scripts in filename order.

    Args:
        sql_dir: Root folder holding one subfolder per layer.
        layer: Subfolder name, e.g. ``"setup"``, ``"silver"``, ``"gold"`` or ``"queries"``.
        patterns: Optional filename globs (e.g. ``["050_*"]``). A pattern
            without ``.sql`` also matches with it appended, so ``050_*`` and
            ``050_*.sql`` behave the same. Matches everything when empty.

    Raises:
        FileNotFoundError: ``sql_dir`` does not exist.
    """
    if not sql_dir.is_dir():
        raise FileNotFoundError(f'SQL script directory not found: {sql_dir}')
    scripts = sorted((sql_dir / layer).glob('*.sql'))
    if not patterns:
        return scripts
    return [
        s for s in scripts
        if any(fnmatch(s.name, p) or fnmatch(s.name, p + '.sql') for p in patterns)
    ]


def run_scripts(conn: sqlite3.Connection, scripts: list[Path]) -> None:
    """Run each script in order, stopping at the first failure."""
    for script in scripts:
        print(f'Running {script.parent.name}/{script.name}...')
        run_sql_file(conn, script)
        print('\tdone')


def run_query(conn: sqlite3.Connection, sql_dir: Path, name: str,
              params: Mapping[str, Any]) -> tuple[list[str], list[tuple]]:
    """Run a parameterised query from ``sql/queries/<name>.sql`` and return its rows.

    Args:
        conn: Open connection.
        sql_dir: Root folder holding the ``queries`` subfolder.
        name: Script name, with or without ``.sql``.
        params: Values for the script's ``:name`` placeholders.

    Returns:
        The column names and the rows of the script's last statement.

    Raises:
        FileNotFoundError: No query has that name. The message lists the available ones.
        sqlite3.ProgrammingError: A placeholder in the query has no value in ``params``.
    """
    scripts = discover_scripts(sql_dir, 'queries', [name])
    if not scripts:
        available = ', '.join(s.stem for s in discover_scripts(sql_dir, 'queries')) or 'none'
        raise FileNotFoundError(f'No query named {name!r} in {sql_dir / "queries"} (available: {available})')

    cursor = None
    for statement in split_statements(scripts[0].read_text(encoding='utf-8')):
        cursor = conn.execute(statement, params)
    return [d[0] for d in cursor.description], cursor.fetchall()
