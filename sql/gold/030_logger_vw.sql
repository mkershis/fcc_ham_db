-- Minimal callsign lookup for logging applications.
DROP VIEW IF EXISTS gold_logger;

CREATE VIEW gold_logger AS
SELECT
    callsign AS callsign
    ,CASE WHEN first_name IS NOT NULL
        THEN UPPER(SUBSTR(first_name, 1, 1)) || LOWER(SUBSTR(first_name, 2))
        ELSE entity_name END AS name
    ,city || ', ' || UPPER(state) AS location
    ,operator_class AS operator_class
    ,CASE WHEN expired_date <= DATE('now', 'localtime')
            OR cancellation_date <= DATE('now', 'localtime')
        THEN 'Expired' ELSE 'Active' END AS license_status
FROM gold_summary;
