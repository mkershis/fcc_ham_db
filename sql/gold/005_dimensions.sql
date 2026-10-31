-- Lookup tables that spell out the one-letter codes.
DROP TABLE IF EXISTS gold_op_class_map;
CREATE TABLE gold_op_class_map (
    op_class_code TEXT PRIMARY KEY,
    op_class_name TEXT NOT NULL
);
INSERT INTO gold_op_class_map VALUES
    ('A', 'Advanced'),
    ('E', 'Extra'),
    ('G', 'General'),
    ('N', 'Novice'),
    ('P', 'Technician Plus'),
    ('T', 'Technician');

DROP TABLE IF EXISTS gold_status_map;
CREATE TABLE gold_status_map (
    status_code TEXT PRIMARY KEY,
    status      TEXT NOT NULL
);
INSERT INTO gold_status_map VALUES
    ('A', 'Active'),
    ('C', 'Canceled'),
    ('E', 'Expired'),
    ('L', 'Pending Legal Status'),
    ('P', 'Parent Station Canceled'),
    ('T', 'Terminated'),
    ('X', 'Term Pending');
