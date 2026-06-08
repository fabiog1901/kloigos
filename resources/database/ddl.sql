CREATE TABLE servers (
    hostname TEXT NOT NULL,
    private_ip TEXT NOT NULL,
    public_ip TEXT NULL,
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
    compute_id TEXT NOT NULL GENERATED ALWAYS AS (hostname || '-cu' || lpad(ordinal::TEXT, 2, '0')) STORED,
    hostname TEXT NOT NULL,
    ordinal INT2 NOT NULL,
    cpu_range TEXT NOT NULL,
    cpu_count INT2 NOT NULL,
    cpu_set TEXT NOT NULL,
    private_ip TEXT NOT NULL,
    public_ip TEXT NULL,
    cu_user TEXT NOT NULL,
    STATUS TEXT NOT NULL,
    started_at TIMESTAMPTZ NULL,
    tags JSONB NULL,
    CONSTRAINT pk_compute_units PRIMARY KEY (compute_id),
    CONSTRAINT uq_compute_units_hostname_ordinal UNIQUE (hostname, ordinal),
    CONSTRAINT uq_compute_units_hostname_private_ip UNIQUE (hostname, private_ip),
    CONSTRAINT hostname_in_servers FOREIGN KEY (hostname) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_compute_units_public_ip
ON compute_units (public_ip)
WHERE public_ip IS NOT NULL;

-- Framework tables such as cpkit.playbooks, cpkit.event_log,
-- cpkit.api_keys, and cpkit.settings are owned by cpkit.
-- Apply cpkit's resources/ddl.sql before this application schema.
