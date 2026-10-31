-- Values the silver build could not fit to the declared type (they become NULL in silver).
CREATE TABLE IF NOT EXISTS silver_dq_rejects (
    table_name    TEXT NOT NULL,
    column_name   TEXT NOT NULL,
    uid           TEXT,
    raw_value     TEXT,
    expected_type TEXT NOT NULL,
    rejected_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
