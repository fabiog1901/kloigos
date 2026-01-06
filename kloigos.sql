-- cockroachdb schema

USE defaultdb;

DROP DATABASE IF EXISTS kloigos;

CREATE DATABASE kloigos;

USE kloigos;

CREATE TABLE compute_units (
    compute_id STRING NOT NULL,
    cpu_count INT2 NOT NULL,
    cpu_range STRING NOT NULL,
    hostname STRING NOT NULL,
    ip STRING NOT NULL,
    region STRING NOT NULL,
    zone STRING NOT NULL,
    status STRING NOT NULL,
    started_at TIMESTAMPTZ NULL,
    tags JSONB NOT NULL DEFAULT '{}':::JSONB,
    CONSTRAINT pk PRIMARY KEY (compute_id ASC)
);

CREATE TABLE playbooks (
    id STRING NOT NULL,
    content BYTES NULL,
    CONSTRAINT pk PRIMARY KEY (id ASC)
);
