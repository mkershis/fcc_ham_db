"""Silver layer: typed, validated, normalised tables built from bronze with generated SQL.

Each table's SQL is generated from its ``schema/<table>.toml`` control file, so
the declared types are defined in exactly one place. A value that doesn't fit
its declared type becomes NULL in silver and is logged in ``silver_dq_rejects``.
"""

import sqlite3
from decimal import Decimal

from .config import SilverConfig
from .db import transaction
from .schema import Column, TableSchema

LAYER = 'silver'
SOURCE_LAYER = 'bronze'

_MAX_INT = 2_147_483_647  # the largest value of the `int` type


def _validated_expression(column: Column, src: str) -> str:
    """SQL that converts a raw text value to its declared type, or NULL if it doesn't fit.

    Surrounding whitespace is trimmed and an empty value is NULL. No
    normalisation is applied; see :func:`clean_expression`.

    Raises:
        ValueError: The column's type has no conversion defined.
    """
    v = f"NULLIF(TRIM({src}.\"{column.name}\"), '')"
    kind, length, precision, scale = column.type.kind, column.type.length, column.type.precision, column.type.scale

    if kind in ('char', 'varchar'):
        return f'CASE WHEN LENGTH({v}) <= {length} THEN {v} END'
    if kind == 'date':
        # raw mm/dd/yyyy -> ISO yyyy-mm-dd; the round trip through date() rejects e.g. 02/30
        iso = f"SUBSTR({v}, 7, 4) || '-' || SUBSTR({v}, 1, 2) || '-' || SUBSTR({v}, 4, 2)"
        return (f"CASE WHEN {v} GLOB '[0-1][0-9]/[0-3][0-9]/[0-9][0-9][0-9][0-9]' "
                f'AND DATE({iso}) = {iso} THEN {iso} END')
    if kind == 'int':
        return (f"CASE WHEN {v} NOT GLOB '*[^0-9]*' AND LENGTH({v}) <= 10 "
                f'AND CAST({v} AS INTEGER) <= {_MAX_INT} THEN CAST({v} AS INTEGER) END')
    if kind == 'numeric' and scale == 0:
        return f"CASE WHEN {v} NOT GLOB '*[^0-9]*' AND LENGTH({v}) <= {precision} THEN CAST({v} AS INTEGER) END"
    if kind == 'numeric':
        limit = format(Decimal(10) ** (precision - scale) - Decimal(10) ** -scale, 'f')
        return (f"CASE WHEN {v} NOT GLOB '*[^0-9.]*' AND {v} NOT GLOB '*.*.*' AND {v} GLOB '*[0-9]*' "
                f'AND CAST({v} AS REAL) <= {limit} THEN CAST({v} AS REAL) END')
    raise ValueError(f'No conversion defined for {column.type!r}')


def clean_expression(column: Column, src: str, normalise: bool = True) -> str:
    """SQL expression producing a column's silver value from the bronze row ``src``.

    Args:
        column: Column definition from the control file.
        src: Alias of the bronze table in the query.
        normalise: Apply the column's ``clean`` rule (title/upper case). Left
            off when only checking whether the value is valid.
    """
    expr = _validated_expression(column, src)
    if normalise and column.clean == 'title':
        return f'title_case({expr})'
    if normalise and column.clean == 'upper':
        return f'UPPER({expr})'
    return expr


def create_table_sql(schema: TableSchema, target: str) -> str:
    """``CREATE TABLE`` statement for a silver table, typed from the control file.

    Args:
        schema: Control-file definition for the table.
        target: Name (without prefix) of the table to create.
    """
    columns = ',\n    '.join(f'"{c.name}" {c.type.sqlite_type}' for c in schema.columns)
    return f'CREATE TABLE "{LAYER}_{target}" (\n    {columns}\n)'


def insert_select_sql(schema: TableSchema, target: str) -> str:
    """``INSERT ... SELECT`` statement filling a silver table from bronze.

    Args:
        schema: Control-file definition for the table.
        target: Name (without prefix) of the table to fill.
    """
    names = ', '.join(f'"{c.name}"' for c in schema.columns)
    select_list = ',\n    '.join(clean_expression(c, 'b') for c in schema.columns)
    return (f'INSERT INTO "{LAYER}_{target}" ({names})\n'
            f'SELECT\n    {select_list}\n'
            f'FROM "{SOURCE_LAYER}_{schema.table}" AS b')


def rejects_sql(schema: TableSchema) -> str:
    """``INSERT`` statement logging every non-empty raw value that converts to NULL."""
    selects = '\nUNION ALL\n'.join(
        f"SELECT '{schema.table}', '{c.name}', CAST(b.\"uid\" AS TEXT), b.\"{c.name}\", '{c.type}'\n"
        f'FROM "{SOURCE_LAYER}_{schema.table}" AS b\n'
        f"WHERE NULLIF(TRIM(b.\"{c.name}\"), '') IS NOT NULL "
        f"AND ({clean_expression(c, 'b', normalise=False)}) IS NULL"
        for c in schema.columns
    )
    return (f'INSERT INTO {LAYER}_dq_rejects (table_name, column_name, uid, raw_value, expected_type)\n'
            f'{selects}')


def build_table(conn: sqlite3.Connection, schema: TableSchema, settings: SilverConfig) -> None:
    """Rebuild one silver table from its bronze table.

    The new table is built under a temporary name and swapped in within a
    single transaction, so a failure leaves the existing table intact.
    """
    table, new = f'{LAYER}_{schema.table}', f'{schema.table}_new'
    print(f'Building "{table}"...')

    with transaction(conn):
        conn.execute(f'DROP TABLE IF EXISTS "{LAYER}_{new}"')
        conn.execute(create_table_sql(schema, new))
        conn.execute(insert_select_sql(schema, new))

        conn.execute(f'DELETE FROM {LAYER}_dq_rejects WHERE table_name = ?', (schema.table,))
        if settings.log_rejects:
            conn.execute(rejects_sql(schema))

        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'ALTER TABLE "{LAYER}_{new}" RENAME TO "{table}"')
        # index names are database-wide, so these are created only after the old table is gone
        for col in schema.indexes:
            conn.execute(f'CREATE INDEX "idx_{table}_{col}" ON "{table}"("{col}")')
    print(f'\tTable "{table}" was built')


def build_all(conn: sqlite3.Connection, schemas: list[TableSchema], settings: SilverConfig) -> None:
    """Rebuild every silver table described by ``schemas``."""
    for schema in schemas:
        build_table(conn, schema, settings)
