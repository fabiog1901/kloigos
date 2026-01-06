# Architecture overview

Kloigos is designed as a **stateless, highly available control plane** that manages compute units across one or more hosts using native Linux primitives. Its architecture cleanly separates the user interface, control logic, and persistent state, allowing each layer to scale and fail independently.

## Core components

Kloigos is composed of three main components:

### Web application

The web application provides a user-facing interface for interacting with Kloigos. It allows users to view compute units, inspect their state, and perform lifecycle operations directly from the browser.

The web application is **fully stateless**. It does not store any local state and communicates exclusively with the Kloigos backend through its APIs. As a result, multiple instances of the web application can be deployed behind a load balancer to provide high availability and horizontal scalability.

### Backend service

The backend is implemented as a FastAPI application and serves as the control plane for Kloigos. It exposes APIs for provisioning, deprovisioning, and managing compute units, and coordinates all actions across hosts.

To perform host-level operations—such as creating users, configuring systemd slices, setting up filesystem paths, or enforcing network policies—the backend delegates execution to **Ansible**, using `ansible-runner`. All operational logic is externalized into Ansible playbooks, keeping the backend thin and focused on orchestration rather than configuration details.

Like the web application, the backend is **completely stateless**. It does not rely on local files or persistent storage, and any backend instance can handle any request. This enables multiple backend instances to run concurrently for redundancy and load sharing.

### Persistent state (CockroachDB)

All Kloigos state is stored in **CockroachDB**, which serves as the single source of truth for the system. This includes:

* compute unit definitions and metadata
* allocation and deallocation state
* host information
* user and resource mappings
* versioned Ansible playbooks (stored as compressed artifacts)

By relying on CockroachDB’s distributed, replicated architecture, Kloigos avoids single points of failure and supports strong consistency across multiple backend instances. The database ensures that all controllers observe the same state and can safely coordinate actions in a highly available setup.

## High availability by design

Because both the web application and the backend are stateless, they can be deployed on multiple servers without coordination between instances. High availability is achieved by:

* running multiple web application instances behind a load balancer
* running multiple backend instances in parallel
* using CockroachDB for durable, replicated state and coordination

If a web or backend instance fails, traffic can be routed to another instance without loss of state or disruption to ongoing operations. All metadata and operational definitions, including playbooks, are preserved in the database.

## Summary

Kloigos follows a simple but robust architectural model:

* **stateless control plane** (web app + backend)
* **externalized execution** via Ansible
* **strongly consistent, replicated state** in CockroachDB

This design allows Kloigos to scale horizontally, tolerate failures, and manage compute units reliably without introducing complex orchestration layers or runtime dependencies.
