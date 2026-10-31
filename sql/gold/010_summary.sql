-- One row per callsign, from the most recent owner of that callsign.
DROP TABLE IF EXISTS gold_summary;

CREATE TABLE gold_summary AS
WITH ranked AS (
    SELECT hd.uid
        ,ROW_NUMBER() OVER (PARTITION BY hd.callsign ORDER BY hd.effective_date DESC, hd.uid DESC) AS recent_rn
    FROM silver_hd AS hd
    JOIN silver_en AS en
        ON hd.uid = en.uid
),
current_owner AS (
    SELECT uid FROM ranked WHERE recent_rn = 1
)
SELECT
    en.callsign
    ,COALESCE(ocm.op_class_name, CASE WHEN am.operator_class IS NULL THEN 'Club' ELSE 'Unknown' END) AS operator_class
    ,am.region_code
    ,am.trustee_callsign
    ,am.trustee_name
    ,en.entity_name
    ,en.first_name
    ,en.last_name
    ,en.address
    ,en.po_box
    ,en.city
    ,en.state
    ,en.zip_code
    ,COALESCE(sm.status, 'Unknown') AS license_status
    ,hd.grant_date
    ,hd.effective_date
    ,hd.expired_date
    ,hd.cancellation_date
FROM silver_en AS en
JOIN silver_hd AS hd
    ON en.uid = hd.uid
JOIN current_owner AS c
    ON c.uid = en.uid
LEFT JOIN silver_am AS am
    ON am.uid = en.uid
LEFT JOIN gold_op_class_map AS ocm
    ON ocm.op_class_code = am.operator_class
LEFT JOIN gold_status_map AS sm
    ON sm.status_code = hd.license_status;

CREATE INDEX idx_gold_summary_callsign ON gold_summary(callsign);
CREATE INDEX idx_gold_summary_last_name ON gold_summary(last_name);
CREATE INDEX idx_gold_summary_city ON gold_summary(city);
CREATE INDEX idx_gold_summary_state ON gold_summary(state);
