PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE compute_units (
    compute_id TEXT PRIMARY KEY,
    cpu_count INTEGER NOT NULL,
    cpu_range TEXT NOT NULL,
    hostname TEXT NOT NULL,
    ip TEXT NOT NULL,
    region TEXT NOT NULL,
    zone TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP NULL,
    tags TEXT NOT NULL DEFAULT '{}'
);
INSERT INTO compute_units VALUES('ec2-3-250-173-37_c0-3',4,'0-3','ec2-3-250-173-37','3.250.173.37','trikolona','a','free',NULL,'{"deployment_id": "fabiodd", "owner":"fab"}');
INSERT INTO compute_units VALUES('ec2-3-250-173-37_c4-7',4,'4-7','ec2-3-250-173-37','3.250.173.37','trikolona','a','free',NULL,'{}');
INSERT INTO compute_units VALUES('ec2-34-247-86-193_c0-7-2',4,'0-7:2','ec2-34-247-86-193','34.247.86.193','benelux','c','free',NULL,'{}');
INSERT INTO compute_units VALUES('ec2-34-247-86-193_c1-7-2',4,'1-7:2','ec2-34-247-86-193','34.247.86.193','benelux','c','free',NULL,'{}');
CREATE INDEX idx_compute_units_region ON compute_units(region);
CREATE INDEX idx_compute_units_status ON compute_units(status);
CREATE INDEX idx_compute_units_hostname ON compute_units(hostname);
COMMIT;
