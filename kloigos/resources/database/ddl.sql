-- kloigos tables
CREATE TABLE IF NOT EXISTS servers (
    hostname TEXT NOT NULL,
    private_ip TEXT NOT NULL,
    public_ip TEXT NULL,
    server_admin_user TEXT NOT NULL,
    region TEXT NOT NULL,
    zone TEXT NOT NULL,
    runtime_profile TEXT NOT NULL DEFAULT 'standard',
    STATUS TEXT NOT NULL,
    cpu_count int2 NULL,
    mem_gb int2 NULL,
    disk_count int2 NULL,
    disk_size_gb int2 NULL,
    health_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    last_health_check_at TIMESTAMPTZ NULL,
    last_health_error TEXT NULL,
    last_healthy_at TIMESTAMPTZ NULL,
    tags JSONB NULL,
    CONSTRAINT pk_servers PRIMARY KEY (hostname)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGSERIAL NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ NULL,
    message TEXT NOT NULL,
    details JSONB NULL,
    CONSTRAINT pk_alerts PRIMARY KEY (alert_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_resource
ON alerts (alert_type, resource_type, resource_id)
WHERE status = 'OPEN';

INSERT INTO cpkit.mq (msg_type, start_after)
SELECT 'SERVER_HEALTH_CHECK', now() + INTERVAL '60s' + (random() * INTERVAL '10s')
WHERE NOT EXISTS (
    SELECT 1
    FROM cpkit.mq
    WHERE msg_type = 'SERVER_HEALTH_CHECK'
);

CREATE TABLE IF NOT EXISTS compute_units (
    compute_id TEXT NOT NULL GENERATED ALWAYS AS (hostname || '-cu' || lpad(ordinal::TEXT, 2, '0')) STORED,
    hostname TEXT NOT NULL,
    ordinal INT2 NOT NULL,
    cpu_range TEXT NOT NULL,
    cpu_count INT2 NOT NULL,
    cpu_set TEXT NOT NULL,
    STATUS TEXT NOT NULL,
    allocation_id TEXT NULL,
    started_at TIMESTAMPTZ NULL,
    tags JSONB NULL,
    CONSTRAINT pk_compute_units PRIMARY KEY (compute_id),
    CONSTRAINT uq_compute_units_hostname_ordinal UNIQUE (hostname, ordinal),
    CONSTRAINT hostname_in_servers FOREIGN KEY (hostname) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ip_pool (
    ip_address TEXT NOT NULL,
    status TEXT NOT NULL,
    allocation_id TEXT NULL,
    current_host TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_ip_pool PRIMARY KEY (ip_address),
    CONSTRAINT current_host_in_servers FOREIGN KEY (current_host) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS allocations (
    allocation_id TEXT NOT NULL,
    login_user TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    compute_id TEXT NULL,
    current_host TEXT NULL,
    status TEXT NOT NULL,
    tags JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_allocations PRIMARY KEY (allocation_id),
    CONSTRAINT allocation_compute_unit FOREIGN KEY (compute_id) REFERENCES compute_units(compute_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT allocation_current_host FOREIGN KEY (current_host) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_allocations_active_login_user
ON allocations (login_user)
WHERE status <> 'DEALLOCATED';

CREATE UNIQUE INDEX IF NOT EXISTS uq_allocations_compute_id
ON allocations (compute_id)
WHERE compute_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_allocations_allocated_ip_address
ON allocations (ip_address)
WHERE status = 'ALLOCATED';

ALTER TABLE compute_units DROP CONSTRAINT IF EXISTS compute_unit_allocation;

ALTER TABLE compute_units
ADD CONSTRAINT compute_unit_allocation FOREIGN KEY (allocation_id) REFERENCES allocations(allocation_id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ip_pool DROP CONSTRAINT IF EXISTS ip_pool_allocation;

ALTER TABLE ip_pool
ADD CONSTRAINT ip_pool_allocation FOREIGN KEY (allocation_id) REFERENCES allocations(allocation_id) ON UPDATE CASCADE ON DELETE SET NULL;
