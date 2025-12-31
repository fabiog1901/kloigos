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

---

## Use case for Kloigos

Kloigos can be broadly useful - but only for a specific class of users and environments.
It’s not a universal replacement for VMs, containers, or Kubernetes, and that’s actually a strength, not a weakness.

Let’s frame this clearly.

## 1. What problem Kloigos _really_ solves

At its core, Kloigos solves this problem:

> “How do I safely and efficiently subdivide a large Linux server into multiple _VM-like_ environments **without** a hypervisor or container stack, while keeping a familiar SSH + systemd user experience?”

That problem exists **far more often than people realize**, especially outside hyperscale cloud-native teams.

Kloigos is most compelling where people want:

- **strong isolation**
- **very low overhead**
- **standard Linux tooling**
- **no Kubernetes**
- **no hypervisor**
- **no image pipelines**

---

## 2. Who would find Kloigos immediately useful

### 1) Infrastructure / platform teams with large bare-metal servers

Common in:

- finance / trading
- telco
- research labs
- enterprise data centers
- on-prem AI / ML clusters

These teams often have:

- 64-256 core machines
- predictable workloads
- strong isolation requirements
- skepticism toward Kubernetes overhead

Kloigos lets them:

- slice machines deterministically
- assign ownership cleanly
- avoid VM sprawl
- keep performance predictable

---

### 2) Teams running “pet services” rather than cattle

Not every workload fits the container model.

Examples:

- stateful services
- legacy daemons
- services that expect a writable filesystem
- software that assumes SSH access
- systemd-managed services
- licensed software bound to host identity

Kloigos gives them:

- isolation without rewriting deployment models
- an EC2-like mental model
- predictable CPU and IO placement

---

### 3) Multi-tenant environments with _trusted but isolated_ users

Examples:

- internal developer platforms
- shared build servers
- CI runners
- academic compute clusters
- training environments

These environments need:

- real isolation
- fair resource usage
- simple cleanup
- minimal ops burden

Kloigos fits perfectly here.

---

### 4) Performance-sensitive workloads

Kloigos avoids:

- VM exits
- container overlay filesystems
- network overlays
- extra scheduler layers

This matters for:

- low-latency services
- HPC-style workloads
- NUMA-sensitive applications
- IO-heavy pipelines

---

## 3. Where Kloigos is _not_ a good fit

Kloigos is _not_ ideal for:

- untrusted internet-facing tenants (shared kernel risk)
- workloads needing strong kernel isolation guarantees
- ephemeral, stateless, image-based microservices
- teams deeply invested in Kubernetes
- workloads that rely on container ecosystems (sidecars, service mesh, etc.)

Those users should stick with:

- Kubernetes
- microVMs (Firecracker)
- traditional VMs

---

## 4. How wide is the adaptability?

### Conceptually

Kloigos is adaptable to **any environment that already runs Linux and systemd**.

It does not require:

- special kernels
- special hardware
- custom runtimes
- vendor lock-in

That makes it _portable_ and _incrementally adoptable_.

---

### Practically

Kloigos is best described as:

> **“A Linux-native, VM-like abstraction layer for subdividing large machines.”**

That’s a niche - but it’s a **real and recurring niche**, and it’s underserved by existing tools.

---

## 5. Why this niche exists (and persists)

Many teams are stuck between:

- **VMs** → too heavy, too expensive
- **Containers** → too opinionated, too complex, too ephemeral

Kloigos occupies the missing middle ground:

- stronger isolation than “just users”
- simpler than Kubernetes
- lighter than VMs
- more flexible than containers

This “middle ground” is surprisingly common in real-world ops.

---

## 6. The strongest argument for Kloigos

The strongest argument isn’t technical—it’s experiential:

> “Give a developer SSH access, systemd, predictable resources, and no surprises.”

That’s an incredibly powerful value proposition.

Many engineers **want**:

- a small VM
- with guaranteed CPU and IO
- without having to understand Kubernetes internals

Kloigos delivers exactly that.

---

## 7. Final honest assessment

Kloigos is not for everyone - and that’s okay.

It is:

- ❌ not a general-purpose cloud platform
- ❌ not a Kubernetes replacement
- ❌ not a security boundary for hostile tenants

But it _is_:

- ✅ a compelling alternative for a real, underserved segment
- ✅ technically sound
- ✅ operationally elegant
- ✅ easy to reason about
- ✅ easy to adopt incrementally

We present Kloigos clearly as:

> **“VM-like compute units without VMs, built from native Linux primitives”**

---

## Κλοηγός / Kloigos API (v0.2.0)

**Base URL:** `/api`

## 🗂️ compute_units

### 🟩 `POST /compute_units/allocate`

Allocate

**Request body (JSON):** `ComputeUnitRequest`

**Responses:**

- ✅ `200` → `ComputeUnitResponse`

- ❌ `422` → `HTTPValidationError`

### 🟥 `DELETE /compute_units/deallocate/{compute_id}`

Deallocate

**Parameters:**

- ❗ `compute_id` 🔤

**Responses:**

- ✅ `200` → `{}`

- ❌ `422` → `HTTPValidationError`

### 🟦 `GET /compute_units/`

List Servers

Returns a list of all servers.
Optionally filter the results by 'deployment_id' or 'status' query parameters.

Example:
- /servers
- /servers?deployment_id=web_app_v1
- /servers?status=free

**Parameters:**

- ➖ `compute_id` 🔤 🚫
- ➖ `hostname` 🔤 🚫
- ➖ `region` 🔤 🚫
- ➖ `zone` 🔤 🚫
- ➖ `cpu_count` 🔢 🚫
- ➖ `deployment_id` 🔤 🚫
- ➖ `status` 🔤 🚫

**Responses:**

- ✅ `200` → `array[ComputeUnitResponse]`

- ❌ `422` → `HTTPValidationError`

## 🗂️ admin

### 🟩 `POST /admin/init_server`

Init Server

**Request body (JSON):** `InitServerRequest`

**Responses:**

- ✅ `200` → `{}`

- ❌ `422` → `HTTPValidationError`

### 🟥 `DELETE /admin/decommission_server/{hostname}`

Decommission Server

**Parameters:**

- ❗ `hostname` 🔤

**Responses:**

- ✅ `200` → `{}`

- ❌ `422` → `HTTPValidationError`

---

## Schemas

### ComputeUnitRequest

**Required:**

- `tags 📦 🚫`
- `ssh_public_key 🔤`

**Optional:**

- `cpu_count` 🔢 🚫 default: `4`
- `region` 🔤 🚫
- `zone` 🔤 🚫

### ComputeUnitResponse

**Required:**

- `ports_range 🔤 🚫`
- `ip 🔤`
- `zone 🔤`
- `compute_id 🔤`
- `started_at 🔤 🚫`
- `region 🔤`
- `hostname 🔤`
- `cpu_count 🔢`
- `status 🔤`
- `tags 📦 🚫`
- `cpu_range 🔤`
- `cpu_list 🔤`

### HTTPValidationError

**Optional:**

- `detail` array[ValidationError]

### InitServerRequest

**Required:**

- `ip 🔤`
- `zone 🔤`
- `region 🔤`
- `hostname 🔤`
- `cpu_ranges array[🔤]`

### ValidationError

**Required:**

- `type 🔤`
- `msg 🔤`
- `loc array[🔤 🔢]`
