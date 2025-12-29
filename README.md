# Kloigos | Κλοηγός

Ultrasimple micro [CMDB](https://en.wikipedia.org/wiki/Configuration_management_database) for managing local servers.

The name comes from the Greek word **πλοηγός** (ploigos), which means "navigator", but substituting **π** (Pi) with **Κ** (Kappa), so **Κλοηγός**.

![dashboard](media/dashboard.png)

## What problem it solves

Imagine you manage a fleet of large servers - machines with 64 or 128 CPUs, spread across 1, 2, or even 4 NUMA nodes.

You can use each server to run a single application that consumes all available CPUs, or you can partition the CPUs into smaller _compute units_ so that multiple applications can share the same machine.

For example, on a 64-CPU server, you might split the system into two 32-CPU compute units.

The most common way to achieve this today is by introducing a virtualization layer, such as a hypervisor to run multiple virtual machines, or a container orchestrator like Kubernetes. These solutions are mature, feature-rich, and well supported. However, they also come with costs: licensing fees, operational complexity, and non-trivial CPU overhead to run the virtualization or orchestration layer itself.

This is where **Kloigos** offers an alternative approach.

Kloigos lets you manage compute units directly on the host, without introducing an additional abstraction layer. Each compute unit is identified by a combination of the hostname and a specific CPU range, and is treated as an independent execution environment. You can install and run any software you like within each compute unit, much like you would on a lightweight virtual machine.

Kloigos relies exclusively on native Linux primitives and systemd facilities, introducing no additional runtime overhead and requiring no special software stack such as hypervisors or container orchestrators.

### Resource isolation and control

Each compute unit is mapped to a dedicated Unix user and a corresponding systemd user slice. This slice is used to enforce hard resource boundaries, including:

- a fixed set of CPUs assigned via `AllowedCPUs`,
- optional limits on memory usage, process count, and I/O bandwidth,
- persistent enforcement across all processes and services started by the user.

This ensures that workloads running in one compute unit cannot consume resources allocated to another.

### Network isolation

To prevent port conflicts and enforce clear network boundaries, Kloigos assigns each compute unit a dedicated port range. Port usage is enforced at the host level using **nftables**, restricting each compute unit’s user to bind only to its allocated range. This guarantees isolation even for ad-hoc processes and user-managed services.

### Filesystem isolation

Each compute unit is also assigned a set of dedicated filesystem paths, owned exclusively by its Unix user:

- `/opt/<unit>` for binaries and application code,
- `/mnt/<unit>` for data volumes, backed by a dedicated disk,
- `/home/<user>` for user data and configuration.

These paths are writable only by the compute unit’s user and can be size-limited using filesystem quotas, ensuring predictable disk usage and clean separation between units.

### Example

For example, consider a 32-CPU server `host1`, split into two 16-CPU compute units:

```yaml
compute_id: host1_0-15
hostname: host1
cpu_range: 0-15
ports_range: 2000-2200
user: u0-15
```

```yaml
compute_id: host1_16-31
hostname: host1
cpu_range: 16-31
ports_range: 2200-2400
user: u16-31
```

A service deployed on `host1_0-15` would:

- install binaries under `/opt/c0-15/`,
- store data under `/mnt/c0-15/`,
- run as user `u0-15`,
- bind only to ports in the `2000-2200` range,
- execute exclusively on CPUs `0-15` via the compute unit’s systemd slice.

The same service deployed on `host1_16-31` would run independently under its own user, filesystem paths, CPU set, and port range.

### Operational model

Compute units are managed in a way similar to AWS EC2 instances, but at a far smaller and more granular scale. Users can SSH into their assigned compute unit, manage files, and run long-lived background services using `systemd --user`, just as they would on a traditional VM.

Kloigos supports full lifecycle management of compute units via its APIs. Provisioning and deprovisioning handle SSH access, process termination, and filesystem cleanup, ensuring that each allocation starts from a clean state.

In addition to the API, Kloigos now provides a web application that allows users to perform all supported API operations directly from the browser, offering a convenient interface for managing compute units while keeping the control plane fully API-driven.

Check in the `examples` folder in this repo for how I use Ansible Playbooks to manage installations and software upgrades.

## Setup

This is a very simple [FastAPI](https://fastapi.tiangolo.com/) app.

For local testing:

- clone the repo
- install requirements using `poetry install`
- recreate the SQLite database file from the dump

    ```bash
    sqlite3 kloigos.sqlite < kloigos.sql
    ```

- run the FastAPI server in dev mode using

    ```bash
    fastapi dev kloigos/main.py 
    ```

Consult the FastAPI docs for the production deployment guide.

### Stateful data

Kloigos uses the lightweight yet powerful SQLite database to store stateful data, such as the
list of compute units and their current status. While a simple text file might be sufficient today,
using a proper relational database provides greater flexibility, richer querying capabilities,
and helps future-proof Kloigos as it evolves.

### Clean up after deprovisioning

Most Kloigos operations involve serving and managing metadata about compute units.
There is, however, one scenario that goes beyond simple metadata updates: the deprovisioning of a compute unit.

When a compute unit is deprovisioned, it is best practice to remove any residual data so
that the unit can be returned to a clean state and made ready for reuse.
To perform this cleanup, Kloigos invokes an Ansible playbook (`clean_up.yaml`)
against the compute unit being terminated.

For this process to work, Ansible must be able to establish an SSH connection to the host.
As a result, the appropriate SSH keys must be available and loaded on the Kloigos server.

---

## API

Consult the API Swagger UI page at `/docs` for info on all endpoints.

![api](media/api.png)
