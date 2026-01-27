-- cockroachdb schema
USE defaultdb;

DROP DATABASE IF EXISTS kloigos;

CREATE DATABASE kloigos;

USE kloigos;

CREATE TABLE servers (
    hostname STRING NOT NULL,
    ip STRING NOT NULL,
    user_id STRING NOT NULL,
    region STRING NOT NULL,
    zone STRING NOT NULL,
    STATUS STRING NOT NULL,
    cpu_count int2 NULL,
    mem_gb int2 NULL,
    disk_count int2 NULL,
    disk_size_gb int2 NULL,
    tags JSONB NULL,
    CONSTRAINT pk PRIMARY KEY (hostname)
);

CREATE TABLE compute_units (
    compute_id STRING NOT NULL AS (hostname || '_' || cpu_range) STORED,
    hostname STRING NOT NULL,
    cpu_range STRING NOT NULL,
    cpu_count INT2 NOT NULL,
    cpu_set STRING NOT NULL,
    port_range STRING NOT NULL,
    cu_user STRING NOT NULL,
    STATUS STRING NOT NULL,
    started_at TIMESTAMPTZ NULL,
    tags JSONB NULL,
    CONSTRAINT pk PRIMARY KEY (compute_id ASC),
    CONSTRAINT hostname_in_servers FOREIGN KEY (hostname) REFERENCES servers(hostname) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE playbooks (
    id STRING NOT NULL,
    content BYTES NULL,
    CONSTRAINT pk PRIMARY KEY (id ASC)
);

CREATE TABLE event_log (
    ts TIMESTAMPTZ NOT NULL,
    user_id STRING NOT NULL,
    ACTION STRING NOT NULL,
    details JSONB NULL,
    CONSTRAINT pk PRIMARY KEY (ts ASC, user_id ASC, ACTION ASC)
);