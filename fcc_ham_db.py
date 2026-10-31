"""Download the FCC ham radio database and build it in SQLite as bronze/silver/gold layers.

Layers (run in this order; pick a subset with --layer):
  setup   always runs first: the data-quality log (sql/setup/)
  bronze  download the FCC data and land it raw in bronze_* tables (schema/*.toml)
  silver  build typed, cleaned silver_* tables from bronze, then run sql/silver/*.sql
  gold    run sql/gold/*.sql (summary table, views, lookups)

Examples:
    python fcc_ham_db.py                            # everything
    python fcc_ham_db.py --skip-download            # reuse the already unpacked files
    python fcc_ham_db.py --layer silver gold        # rebuild from existing bronze, no download
    python fcc_ham_db.py --layer gold --only "050_*"   # just one gold script
    python fcc_ham_db.py --query call_lookup --param call_look=W2ABC
"""

import argparse
import time
from pathlib import Path

from fcc import bronze, silver
from fcc.config import Config, load_config
from fcc.db import connect
from fcc.download import clean_temp_files, download_zip, unpack_zip
from fcc.runner import discover_scripts, run_query, run_scripts
from fcc.schema import load_schemas

DEFAULT_CONFIG = Path(__file__).parent / 'config.toml'
LAYERS = ['bronze', 'silver', 'gold']


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG,
                        help='path to config.toml (default: next to this script)')
    parser.add_argument('--layer', nargs='+', choices=LAYERS, default=LAYERS,
                        help='layers to build (default: all)')
    parser.add_argument('--skip-download', action='store_true',
                        help='bronze: reuse the files already unpacked in the work directory')
    parser.add_argument('--only', nargs='+', metavar='PATTERN',
                        help='only run sql/ scripts matching these filename globs')
    parser.add_argument('--query', metavar='NAME',
                        help='run sql/queries/NAME.sql, print the result and exit (no build)')
    parser.add_argument('--param', action='append', default=[], metavar='KEY=VALUE',
                        help='value for a :KEY placeholder in --query (repeatable)')
    return parser.parse_args(argv)


def parse_params(pairs: list[str]) -> dict[str, int | float | str]:
    """Turn ``KEY=VALUE`` options into query parameters; numbers become numbers."""
    params: dict[str, int | float | str] = {}
    for pair in pairs:
        key, sep, value = pair.partition('=')
        if not sep or not key:
            raise SystemExit(f'--param expects KEY=VALUE, got {pair!r}')
        for convert in (int, float, str):
            try:
                params[key] = convert(value)
                break
            except ValueError:
                continue
    return params


def print_table(columns: list[str], rows: list[tuple]) -> None:
    """Print query results as an aligned text table."""
    cells = [['' if v is None else str(v) for v in row] for row in rows]
    widths = [max([len(name)] + [len(r[i]) for r in cells]) for i, name in enumerate(columns)]
    print('  '.join(name.ljust(w) for name, w in zip(columns, widths)))
    print('  '.join('-' * w for w in widths))
    for row in cells:
        print('  '.join(v.ljust(w) for v, w in zip(row, widths)))
    print(f'({len(rows):,} rows)')


def run(cfg: Config, args: argparse.Namespace) -> None:
    """Run the layers selected by ``args``, always in bronze, silver, gold order."""
    layers = set(args.layer)

    if 'bronze' in layers and not args.skip_download:
        clean_temp_files(cfg.zip_path, cfg.unpacked_dir)
        download_zip(cfg.url, cfg.zip_path, cfg.download)
        unpack_zip(cfg.zip_path, cfg.unpacked_dir)

    conn = connect(cfg.db_path)
    try:
        run_scripts(conn, discover_scripts(cfg.sql_dir, 'setup'))

        schemas = load_schemas(cfg.schema_dir)
        if 'bronze' in layers:
            bronze.load_all(conn, cfg.unpacked_dir, schemas, cfg.load)
        if 'silver' in layers:
            silver.build_all(conn, schemas, cfg.silver)
            run_scripts(conn, discover_scripts(cfg.sql_dir, 'silver', args.only))
        if 'gold' in layers:
            run_scripts(conn, discover_scripts(cfg.sql_dir, 'gold', args.only))
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point."""
    args = parse_args(argv)
    cfg = load_config(args.config)

    if args.query:
        conn = connect(cfg.db_path)
        try:
            print_table(*run_query(conn, cfg.sql_dir, args.query, parse_params(args.param)))
        finally:
            conn.close()
        return

    start = time.time()
    run(cfg, args)
    print(f'Process completed in {round((time.time() - start) / 60, 1)} minutes.')


if __name__ == '__main__':
    main()
