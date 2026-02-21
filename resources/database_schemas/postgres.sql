CREATE TABLE servers (
    hostname TEXT NOT NULL,
    ip TEXT NOT NULL,
    user_id TEXT NOT NULL,
    region TEXT NOT NULL,
    zone TEXT NOT NULL,
    STATUS TEXT NOT NULL,
    cpu_count int2 NULL,
    mem_gb int2 NULL,
    disk_count int2 NULL,
    disk_size_gb int2 NULL,
    tags JSONB NULL,
    CONSTRAINT pk_servers PRIMARY KEY (hostname)
);

CREATE TABLE compute_units (
    compute_id TEXT NOT NULL GENERATED ALWAYS AS (hostname || '_' || cpu_range) STORED,
    hostname TEXT NOT NULL,
    cpu_range TEXT NOT NULL,
    cpu_count INT2 NOT NULL,
    cpu_set TEXT NOT NULL,
    port_range TEXT NOT NULL,
    cu_user TEXT NOT NULL,
    STATUS TEXT NOT NULL,
    started_at TIMESTAMPTZ NULL,
    tags JSONB NULL,
    CONSTRAINT pk_compute_units PRIMARY KEY (compute_id),
    CONSTRAINT hostname_in_servers FOREIGN KEY (hostname) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE playbooks (
    id TEXT NOT NULL,
    content BYTEA NULL,
    CONSTRAINT pk_playbooks PRIMARY KEY (id)
);

CREATE TABLE event_log (
    ts TIMESTAMPTZ NOT NULL,
    user_id TEXT NOT NULL,
    ACTION TEXT NOT NULL,
    details JSONB NULL,
    request_id UUID NULL,
    CONSTRAINT pk_event_log PRIMARY KEY (ts, user_id, ACTION)
);