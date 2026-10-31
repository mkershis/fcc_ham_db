# fcc_ham_db

Builds a local SQLite database from the FCC amateur radio (ULS) callsign data, organised as a medallion architecture. Everything lives in one file, and the layers are told apart by table prefix.

The data comes from the [FCC website](https://www.fcc.gov/uls/transactions/daily-weekly): the `l_amat.zip` file under **Weekly Databases > Licenses**. Field definitions are in the FCC's [database documentation](https://www.fcc.gov/wireless/data/public-access-files-database-downloads).

| Layer | Tables | What it holds |
|---|---|---|
| Bronze | `bronze_*` | The raw `.DAT` data as text, exactly as the FCC delivered it, plus `_source_file` and `_loaded_at` |
| Silver | `silver_*` | Typed, validated, normalised tables (`silver_en`, `silver_hd`, `silver_am`, ...). Values that don't fit their declared type become NULL and are logged in `silver_dq_rejects` |
| Gold | `gold_*` | Business-ready outputs: `gold_summary`, `gold_club_summary_vw`, `gold_logger`, and the code lookups `gold_op_class_map` and `gold_status_map` |

`gold_summary` is the easiest table to work with: one row per callsign, from the most recent owner, with the operator class and license status spelled out. It also carries the trustee name and callsign for clubs.

## Setup
1. Python 3.11 or newer, then `pip install -r requirements.txt`.
2. Optionally edit `config.toml`. The defaults put the downloaded files and the database (`fcc_ham.db`) in a `data/` folder next to the script. The FCC database is over 1.2 GB once built, so make sure there is room.

## Run
```
python fcc_ham_db.py                              # download, then bronze -> silver -> gold
python fcc_ham_db.py --skip-download              # reuse already-unpacked files
python fcc_ham_db.py --layer silver gold          # rebuild from existing bronze (no download, no reload)
python fcc_ham_db.py --layer gold --only "030_*"  # just one gold script
```
A full run takes a few minutes. Re-running is safe: every layer is rebuilt from scratch, and the download is repeated unless `--skip-download` is given.

## Configuration (`config.toml`)
Paths are relative to the config file.

| Section | Setting | Meaning |
|---|---|---|
| `[fcc]` | `url` | Where the zip is downloaded from |
| `[paths]` | `work_dir`, `schema_dir`, `sql_dir` | Download/unpack folder, table control files, SQL scripts |
| `[database]` | `path` | The SQLite file to build |
| `[download]` | `max_retries`, `connect_timeout`, `read_timeout` | Download behaviour |
| `[load]` | `chunksize`, `allow_fewer_rows` | Rows per insert batch; whether bronze may be replaced by a smaller load |
| `[silver]` | `log_rejects` | Turn off the data-quality logging pass for a faster build |

Use `--config path/to/other.toml` to run with a different configuration.

## Extending
- **Change a table:** edit its control file in `schema/` (`pos`, `name`, `type`; types: `char(n)`, `varchar(n)`, `numeric(p,s)`, `date`, `int`). Add a file to add a table. Bronze and silver are both generated from it. List columns in `indexes` to index them in silver.
- **Normalise a text column in silver:** add `clean = "title"` or `clean = "upper"` to the column.
- **Add a table, view or transform:** drop a new `NNN_name.sql` in `sql/gold/` (or `sql/silver/` for extra silver transforms that run after the tables are built). Scripts run in filename order, each in one transaction, and need no changes to the Python code. Statements end with `;`. Make scripts re-runnable (`DROP ... IF EXISTS` first, or `CREATE ... IF NOT EXISTS`).
- `sql/setup/` runs before everything (currently the data-quality log table).

## Queries
SQLite has no stored procedures, so parameterised lookups live in `sql/queries/` as ordinary `.sql` files using `:name` placeholders. They don't run during a build; call them on demand:
```
python fcc_ham_db.py --query call_lookup --param call_look=W2ABC              # one callsign from gold_logger
python fcc_ham_db.py --query recent_suffolk_hams --param days_back=30         # Suffolk County, NY hams licensed in the last N days
```
Add a query by adding a file; `--query` with an unknown name lists the available ones. You can also run any of these files, or your own SQL, in any SQLite client against the `.db` file.

## Safety
Bronze loads into `bronze_<table>_staging` and swaps in one transaction, only if the new data has at least as many rows as the existing table (a truncated download won't wipe good data). Silver tables are likewise built under a temporary name and swapped in, and each SQL script runs in a single transaction, so a failed run never damages a live table.

## Data quality
```sql
SELECT table_name, column_name, expected_type, COUNT(*) AS rejects
FROM silver_dq_rejects
GROUP BY table_name, column_name, expected_type
ORDER BY rejects DESC;
```
The FCC files contain a handful of malformed records (for example, comment text in `co` that spills into the wrong field); these show up here.

## Notes
- The raw tables are no longer named `EN`, `HD`, etc. Use `silver_en`, `silver_hd`, ... (typed) or `bronze_en`, ... (raw text), and `gold_summary` in place of the old `ham_summary`.
- The `last_update` and `row_counts` tables are gone. The load time is in `bronze_*._loaded_at`, and the row-count check happens during the load.
