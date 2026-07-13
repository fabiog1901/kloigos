# Architecture overview

Kloigos is designed as a **stateless, highly available control plane** for a Linux-native bare-metal
Platform as a Service. It manages Compute Units and Allocations across one or more hosts using
standard Linux primitives. Its architecture cleanly separates the user interface, control logic, and
persistent state, allowing each layer to scale and fail independently.

## Core model

Kloigos separates capacity from workload identity.

A **Compute Unit** represents host capacity: CPU allocation, memory limits, NUMA placement, and local
storage. Compute Units are replaceable resource slots.

An **Allocation** represents the durable identity of a workload: allocation ID, Unix login user, IP
address, storage identity, tags, metadata, and current Compute Unit placement. Allocations survive
scaling and migration. When a workload moves, its placement changes but its user, IP address, and
metadata remain stable.

## Core components

Kloigos is composed of three main components:

### Web application

The web application provides a user-facing interface for interacting with Kloigos. It allows users to
view Allocations, Compute Units, servers, jobs, events, playbooks, and administrative resources
directly from the browser.

The web application is **fully stateless**. It does not store any local state and communicates exclusively with the Kloigos backend through its APIs. As a result, multiple instances of the web application can be deployed behind a load balancer to provide high availability and horizontal scalability.

### Backend service

The backend is implemented as a FastAPI application and serves as the control plane for Kloigos. It
exposes APIs for provisioning, deprovisioning, scaling, and managing Allocations and Compute Units,
and coordinates actions across hosts.

To perform host-level operations - such as creating users, configuring systemd slices, setting up
filesystems, assigning floating IPs, installing AppArmor profiles, auditing capabilities, or
enforcing network policies - the backend delegates execution to **Ansible**, using `ansible-runner`.
All infrastructure actions are externalized into versioned, auditable Ansible playbooks, keeping the
backend thin and focused on orchestration rather than configuration details.

Like the web application, the backend is **completely stateless**. It does not rely on local files or persistent storage, and any backend instance can handle any request. This enables multiple backend instances to run concurrently for redundancy and load sharing.

### Persistent state (PostgreSQL)

All Kloigos state is stored in **PostgreSQL**, which serves as the single source of truth for the
system. This includes:

* Compute Unit definitions and metadata
* Allocation identity, placement, and lifecycle state
* host information
* IP pool state
* versioned Ansible playbooks (stored as compressed artifacts)

The database ensures that all controllers observe the same state and can safely coordinate actions.
For highly available deployments, PostgreSQL can be replaced with a PostgreSQL-compatible
distributed database such as CockroachDB.

## High availability by design

Because both the web application and the backend are stateless, they can be deployed on multiple servers without coordination between instances. High availability is achieved by:

* running multiple web application instances behind a load balancer
* running multiple backend instances in parallel
* using PostgreSQL for durable state and coordination

If a web or backend instance fails, traffic can be routed to another instance without loss of state
or disruption to ongoing operations. All metadata and operational definitions, including playbooks,
are preserved in the database.

Deployments that need replicated database state across nodes can use CockroachDB in place of
PostgreSQL, while keeping the same Kloigos control-plane model.

## Summary

Kloigos follows a simple but robust architectural model:

* **stateless control plane** (web app + backend)
* **externalized execution** via versioned Ansible playbooks
* **durable state** in PostgreSQL

This design allows Kloigos to scale horizontally, tolerate failures, and manage bare-metal
application environments reliably without introducing a hypervisor, container runtime, or complex
orchestration layer.
