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

INSERT INTO playbooks (id) values ('CU_ALLOCATE'), ('CU_DEALLOCATE'), ('SERVER_INIT'), ('SERVER_DECOMM');

CREATE TABLE event_log (
    ts TIMESTAMPTZ NOT NULL,
    user_id TEXT NOT NULL,
    ACTION TEXT NOT NULL,
    details JSONB NULL,
    request_id UUID NULL,
    CONSTRAINT pk_event_log PRIMARY KEY (ts, user_id, ACTION)
);

CREATE TABLE api_keys (
    access_key TEXT NOT NULL,
    hashed_secret_access_key BYTEA NOT NULL,
    owner TEXT NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    roles TEXT[],
    CONSTRAINT pk_api_keys PRIMARY KEY (access_key)
);
