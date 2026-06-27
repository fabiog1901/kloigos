alter table if exists ip_pool drop constraint ip_pool_allocation; 
drop table if exists allocations ;                                                                           
drop table if exists ip_pool ;                                                                               
drop table if exists compute_units;                                                                          
drop table if exists servers;                                                                                


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

CREATE TABLE ip_pool (
    ip_address TEXT NOT NULL,
    status TEXT NOT NULL,
    allocation_id TEXT NULL,
    current_host TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_ip_pool PRIMARY KEY (ip_address),
    CONSTRAINT current_host_in_servers FOREIGN KEY (current_host) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE allocations (
    allocation_id TEXT NOT NULL,
    username TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    compute_id TEXT NULL,
    current_host TEXT NULL,
    status TEXT NOT NULL,
    tags JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_allocations PRIMARY KEY (allocation_id),
    CONSTRAINT uq_allocations_username UNIQUE (username),
    CONSTRAINT uq_allocations_ip_address UNIQUE (ip_address),
    CONSTRAINT allocation_ip_in_pool FOREIGN KEY (ip_address) REFERENCES ip_pool(ip_address) ON UPDATE CASCADE,
    CONSTRAINT allocation_compute_unit FOREIGN KEY (compute_id) REFERENCES compute_units(compute_id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT allocation_current_host FOREIGN KEY (current_host) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE UNIQUE INDEX uq_allocations_compute_id
ON allocations (compute_id)
WHERE compute_id IS NOT NULL;

ALTER TABLE ip_pool
ADD CONSTRAINT ip_pool_allocation FOREIGN KEY (allocation_id) REFERENCES allocations(allocation_id) ON UPDATE CASCADE ON DELETE SET NULL;

-- kloigos specific settings
-- INSERT INTO cpkit.settings (
--     key,
--     default_value,
--     value_type,
--     category,
--     is_secret,
--     description
-- ) VALUES
--     ('storage.s3.url',                    '', 'url',     'storage',       false, 'Base S3 endpoint used for tenant external connections.')
-- ON CONFLICT (key) DO NOTHING;

-- kloigos specific playbooks. the yaml content is done via the webapp.
TRUNCATE cpkit.playbooks;

INSERT INTO cpkit.playbooks (name, content, created_by, default_version, updated_by)
VALUES
    ('CU_ALLOCATE'     , NULL, 'system', now():::TIMESTAMPTZ, 'system'),
    ('CU_DEALLOCATE'   , NULL, 'system', now():::TIMESTAMPTZ, 'system'),
    ('ALLOCATION_SCALE', NULL, 'system', now():::TIMESTAMPTZ, 'system'),
    ('SERVER_DECOMM'   , NULL, 'system', now():::TIMESTAMPTZ, 'system'),
    ('SERVER_INIT'     , NULL, 'system', now():::TIMESTAMPTZ, 'system')
;
