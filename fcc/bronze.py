"""Bronze layer: lands the raw FCC .DAT data in SQLite, untouched."""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import LoadConfig
from .db import table_exists, transaction
from .schema import TableSchema

LAYER = 'bronze'


def source_path(unpacked_dir: Path, name: str) -> Path:
    """Locate a .DAT file, ignoring case (the zip's file names differ by platform).

    Raises:
        FileNotFoundError: No file in the folder matches ``name``.
    """
    for path in unpacked_dir.iterdir():
        if path.name.lower() == name.lower():
            return path
    raise FileNotFoundError(f'{name} not found in {unpacked_dir}')


def read_raw(path: Path, schema: TableSchema, chunksize: int) -> pd.io.parsers.TextFileReader:
    """Open one pipe-delimited .DAT file for reading in chunks, with no cleaning or type conversion.

    Every value stays as the text the FCC delivered (empty fields become NULL).
    """
    return pd.read_table(
        path,
        delimiter='|',
        quoting=csv.QUOTE_NONE,  # the files aren't quoted; a stray " would swallow lines
        index_col=False,
        header=None,
        names=[c.name for c in schema.columns],
        usecols=[c.pos - 1 for c in schema.columns],
        dtype='str',
        chunksize=chunksize,
    )


def _literal(value: str) -> str:
    """A SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    """Row count of a table, or 0 if it doesn't exist yet."""
    if not table_exists(conn, table):
        return 0
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def load_table(conn: sqlite3.Connection, unpacked_dir: Path, schema: TableSchema,
               loaded_at: datetime, settings: LoadConfig) -> bool:
    """Load one .DAT file, replacing the live bronze table only if the load succeeds.

    The data goes into ``bronze_<table>_staging`` first. The swap onto the
    live name happens in one transaction, so a failed load leaves the
    existing table untouched. The swap is skipped when the new data has fewer
    rows than the existing table (e.g. a truncated download), unless
    ``settings.allow_fewer_rows`` is set.

    Args:
        conn: Open connection.
        unpacked_dir: Folder holding the unpacked .DAT files.
        schema: Control-file definition for the table.
        loaded_at: Timestamp recorded in the ``_loaded_at`` column.
        settings: Chunk size and row-count policy.

    Returns:
        True if the table was replaced, False if it was kept as is.
    """
    table = f'{LAYER}_{schema.table}'
    staging = f'{table}_staging'
    quoted = [f'"{c.name}"' for c in schema.columns]
    column_defs = ', '.join(f'{q} TEXT' for q in quoted)
    insert = f'INSERT INTO "{staging}" ({", ".join(quoted)}) VALUES ({", ".join("?" * len(quoted))})'

    print(f'Preparing to update "{table}"...')
    with transaction(conn):
        conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
        conn.execute(
            f'CREATE TABLE "{staging}" ({column_defs}, '
            f'_source_file TEXT NOT NULL DEFAULT {_literal(schema.source_file)}, '
            f'_loaded_at TEXT NOT NULL DEFAULT {_literal(loaded_at.isoformat(sep=" ", timespec="seconds"))})'
        )
        for chunk in read_raw(source_path(unpacked_dir, schema.source_file), schema, settings.chunksize):
            rows = chunk.astype(object).where(chunk.notna(), None).to_numpy().tolist()
            conn.executemany(insert, rows)

    new_rows, old_rows = _row_count(conn, staging), _row_count(conn, table)
    if new_rows < old_rows and not settings.allow_fewer_rows:
        conn.execute(f'DROP TABLE "{staging}"')
        print(f'Table "{table}" was not updated (new data has {new_rows:,} rows, existing has {old_rows:,}).')
        return False

    with transaction(conn):
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'ALTER TABLE "{staging}" RENAME TO "{table}"')
    print(f'\tTable "{table}" was updated ({new_rows:,} rows)')
    return True


def load_all(conn: sqlite3.Connection, unpacked_dir: Path, schemas: list[TableSchema],
             settings: LoadConfig) -> None:
    """Read and land every table described by ``schemas``."""
    loaded_at = datetime.now()
    for schema in schemas:
        load_table(conn, unpacked_dir, schema, loaded_at, settings)
