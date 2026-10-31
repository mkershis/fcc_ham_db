-- Clubs alongside their trustee.
DROP VIEW IF EXISTS gold_club_summary_vw;

CREATE VIEW gold_club_summary_vw AS
SELECT
    club.callsign AS club_callsign
    ,club.region_code AS club_region
    ,club.entity_name AS club_name
    ,CASE WHEN club.address IS NULL THEN 'P.O. Box ' || club.po_box
        ELSE club.address END AS club_address
    ,club.city AS club_city
    ,club.state AS club_state
    ,trustee.callsign AS trustee_callsign
    ,trustee.last_name || ', ' || trustee.first_name AS club_trustee
    ,CASE WHEN trustee.address IS NULL THEN 'P.O. Box ' || trustee.po_box
        ELSE trustee.address END AS trustee_address
    ,trustee.city AS trustee_city
    ,trustee.state AS trustee_state
    ,club.expired_date AS club_expire_date
    ,CASE WHEN club.expired_date <= DATE('now') THEN 'Expired' ELSE 'Active' END AS club_lic_status
    ,CASE WHEN trustee.expired_date <= DATE('now') THEN 'Expired' ELSE 'Active' END AS trustee_lic_status
FROM gold_summary AS club
JOIN gold_summary AS trustee
    ON trustee.callsign = club.trustee_callsign
WHERE club.operator_class = 'Club';
