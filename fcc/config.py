"""Loads project settings from ``config.toml``."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DownloadConfig:
    """How the FCC zip file is fetched."""

    max_retries: int = 3
    connect_timeout: int = 10  # seconds to establish the connection
    read_timeout: int = 60  # seconds allowed between chunks


@dataclass(frozen=True)
class LoadConfig:
    """How the raw files are loaded into bronze."""

    chunksize: int = 50_000  # rows read and inserted at a time
    allow_fewer_rows: bool = False  # replace a bronze table even if the new data is smaller


@dataclass(frozen=True)
class SilverConfig:
    """How the silver tables are built."""

    log_rejects: bool = True  # record values that fail type validation in silver_dq_rejects


@dataclass(frozen=True)
class Config:
    """All project settings, with paths resolved to absolute ``Path`` objects."""

    url: str
    work_dir: Path
    schema_dir: Path
    sql_dir: Path
    db_path: Path
    download: DownloadConfig = field(default_factory=DownloadConfig)
    load: LoadConfig = field(default_factory=LoadConfig)
    silver: SilverConfig = field(default_factory=SilverConfig)

    @property
    def zip_path(self) -> Path:
        """Where the downloaded FCC zip file is saved."""
        return self.work_dir / 'ham.zip'

    @property
    def unpacked_dir(self) -> Path:
        """Where the zip file's .DAT files are extracted."""
        return self.work_dir / 'ham'


def load_config(path: str | os.PathLike) -> Config:
    """Read a TOML settings file.

    Args:
        path: Location of ``config.toml``. Relative paths inside it are
            resolved against this file's directory.

    Raises:
        TypeError: A section contains a setting that doesn't exist.
    """
    path = Path(path).resolve()
    with open(path, 'rb') as f:
        raw = tomllib.load(f)

    base = path.parent
    return Config(
        url=raw['fcc']['url'],
        work_dir=base / raw['paths']['work_dir'],
        schema_dir=base / raw['paths']['schema_dir'],
        sql_dir=base / raw['paths']['sql_dir'],
        db_path=base / raw['database']['path'],
        download=DownloadConfig(**raw.get('download', {})),
        load=LoadConfig(**raw.get('load', {})),
        silver=SilverConfig(**raw.get('silver', {})),
    )
