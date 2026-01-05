BEGIN TRANSACTION;
DROP TABLE IF EXISTS "compute_units";
CREATE TABLE "compute_units" (
	"compute_id"	TEXT,
	"cpu_count"	INTEGER NOT NULL,
	"cpu_range"	TEXT NOT NULL,
	"hostname"	TEXT NOT NULL,
	"ip"	TEXT NOT NULL,
	"region"	TEXT NOT NULL,
	"zone"	TEXT NOT NULL,
	"status"	TEXT NOT NULL,
	"started_at"	TIMESTAMP,
	"tags"	TEXT NOT NULL DEFAULT '{}',
	PRIMARY KEY("compute_id")
);
DROP TABLE IF EXISTS "playbooks";
CREATE TABLE playbooks (
	id string not null PRIMARY key,
	content string
);
DROP INDEX IF EXISTS "idx_compute_slots_hostname";
CREATE INDEX idx_compute_slots_hostname ON "compute_units"(hostname);
DROP INDEX IF EXISTS "idx_compute_slots_region";
CREATE INDEX idx_compute_slots_region ON "compute_units"(region);
DROP INDEX IF EXISTS "idx_compute_slots_status";
CREATE INDEX idx_compute_slots_status ON "compute_units"(status);
COMMIT;
