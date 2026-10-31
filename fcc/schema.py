"""Loads table definitions from the TOML control files in ``schema/``."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

CLEAN_RULES = ('title', 'upper', 'zip5')
TEXT_KINDS = ('char', 'varchar')


@dataclass(frozen=True)
class ColumnType:
    """A declared column type from a control file, e.g. ``char(2)`` or ``numeric(9,0)``."""

    kind: str  # char, varchar, numeric, date or int
    length: int | None = None  # char / varchar
    precision: int | None = None  # numeric
    scale: int = 0  # numeric

    @property
    def sqlite_type(self) -> str:
        """Storage type used for the column in silver."""
        if self.kind in TEXT_KINDS or self.kind == 'date':
            return 'TEXT'
        if self.kind == 'int' or (self.kind == 'numeric' and self.scale == 0):
            return 'INTEGER'
        return 'REAL'

    def __str__(self) -> str:
        if self.kind in TEXT_KINDS:
            return f'{self.kind}({self.length})'
        if self.kind == 'numeric':
            return f'numeric({self.precision},{self.scale})'
        return self.kind


@dataclass(frozen=True)
class Column:
    """One column of a source .DAT file."""

    pos: int  # 1-based field position in the pipe-delimited file
    name: str
    type: ColumnType
    clean: str | None = None  # optional text rule applied in silver: "title", "upper" or "zip5"


@dataclass(frozen=True)
class TableSchema:
    """Everything needed to load one .DAT file into one table."""

    table: str
    source_file: str
    indexes: list[str]
    columns: list[Column]


_TYPE_PATTERN = re.compile(r'^(char|varchar|numeric)\((\d+)(?:,\s*(\d+))?\)$')


def parse_type(text: str) -> ColumnType:
    """Convert a type string from a control file into a :class:`ColumnType`.

    Supported: ``char(n)``, ``varchar(n)``, ``numeric(p,s)``, ``date``, ``int``.

    Raises:
        ValueError: The string is not a supported type.
    """
    text = text.strip().lower()
    if text in ('date', 'int'):
        return ColumnType(text)

    match = _TYPE_PATTERN.match(text)
    if not match:
        raise ValueError(f'Unsupported column type: {text!r}')
    kind, first, second = match.groups()
    if kind == 'numeric':
        return ColumnType(kind, precision=int(first), scale=int(second or 0))
    return ColumnType(kind, length=int(first))


def load_table_schema(path: str | Path) -> TableSchema:
    """Read a single table control file.

    Args:
        path: A ``schema/<table>.toml`` file.

    Raises:
        ValueError: A column has an unsupported type, an unknown ``clean``
            rule, a ``clean`` rule on a non-text column, or a repeated
            position or name.
    """
    with open(path, 'rb') as f:
        raw = tomllib.load(f)

    columns = sorted(
        (Column(pos=c['pos'], name=c['name'], type=parse_type(c['type']), clean=c.get('clean'))
         for c in raw['columns']),
        key=lambda c: c.pos,
    )
    for attr in ('pos', 'name'):
        values = [getattr(c, attr) for c in columns]
        if len(values) != len(set(values)):
            raise ValueError(f'{path}: duplicate column {attr}')
    for c in columns:
        if c.clean is None:
            continue
        if c.clean not in CLEAN_RULES:
            raise ValueError(f'{path}: column {c.name!r} has unknown clean rule {c.clean!r}')
        if c.type.kind not in TEXT_KINDS:
            raise ValueError(f'{path}: clean rules only apply to char/varchar ({c.name!r})')

    return TableSchema(
        table=raw['table'],
        source_file=raw['source_file'],
        indexes=raw.get('indexes', []),
        columns=columns,
    )


def load_schemas(schema_dir: str | Path) -> list[TableSchema]:
    """Load every ``*.toml`` control file in a directory, sorted by filename.

    Raises:
        FileNotFoundError: The directory has no ``*.toml`` files.
    """
    paths = sorted(Path(schema_dir).glob('*.toml'))
    if not paths:
        raise FileNotFoundError(f'No *.toml schema files found in {schema_dir}')
    return [load_table_schema(p) for p in paths]
