-- Simple callsign lookup against the gold_logger view.
-- Usage: python fcc_ham_db.py --query call_lookup --param call_look=W2ABC
SELECT * FROM gold_logger
WHERE callsign = UPPER(:call_look);
