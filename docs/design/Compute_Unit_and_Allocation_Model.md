# Compute Unit and Allocation Model

## Purpose

Kloigos separates **execution capacity** from **workload identity**.

This distinction is represented by two core abstractions:

- **Compute Unit (CU)** — the concrete Linux execution boundary in which a workload runs.
- **Allocation** — the durable logical identity of the workload and the resources assigned to it.

The relationship can be summarized as:

> **Compute Units are replaceable execution environments. Allocations are durable workload identities.**

This separation allows Kloigos to change where and how a workload executes without redefining the workload itself.

This document defines the responsibilities, lifecycle boundaries, and architectural invariants of Compute Units and Allocations.

Detailed scheduling, CPU, networking, storage, security, and provisioning behavior is defined in their respective design documents.

---

## Conceptual Model

At a high level:

```text
Physical Host
     │
     │ provides capacity
     ▼
Compute Unit
     │
     │ provides execution environment
     ▼
Allocation
     │
     │ owns workload identity
     ▼
User Workload
```

A physical host contributes resources.

Kloigos selects and reserves those resources and uses them to construct a Compute Unit.

An Allocation is attached to that Compute Unit and the user's workload executes within it.

The important distinction is that the Allocation is not the Compute Unit.

```text
Allocation A
    │
    ├── identity
    ├── configuration
    ├── durable resources
    ├── metadata
    └── history
          │
          ▼
     currently placed on
          │
          ▼
     Compute Unit X
          │
          ▼
       Host 12
```

Later, the same Allocation may instead be placed on another Compute Unit:

```text
Allocation A
    │
    └── currently placed on
          │
          ▼
     Compute Unit Y
          │
          ▼
       Host 27
```

The execution environment changed.

The Allocation did not.

---

## Compute Unit

A Compute Unit is a concrete Linux resource and isolation boundary created on a physical Kloigos host.

It represents the environment in which an Allocation executes.

A Compute Unit may define or enforce resources such as:

- CPU placement or scheduling policy
- memory limits
- process/task limits
- filesystem boundaries
- storage attachment
- Unix execution identity
- network configuration
- IP association
- firewall policy
- security policy

These boundaries are constructed using standard Linux mechanisms rather than a hypervisor or mandatory container runtime.

Depending on the resource model, these mechanisms may include:

- cgroups
- systemd
- cpusets
- Linux scheduler controls
- Unix users and permissions
- filesystems and LVM
- native Linux networking
- nftables
- AppArmor

The exact implementation of these boundaries belongs in the corresponding subsystem design documents.

### Compute Units Are Concrete

A Compute Unit is not merely a database record describing desired capacity.

When active, it corresponds to real resource boundaries enforced by the physical host.

If a CU claims four dedicated CPUs, those CPUs must actually be reserved and enforced for that CU.

If it claims a memory limit, that limit must exist in the host's resource-control hierarchy.

Control-plane state and actual host state must therefore remain consistent.

### Compute Units Are Replaceable

A Compute Unit is not intended to be the permanent identity of the workload.

It may be:

- created
- configured
- activated
- resized through replacement
- reconstructed
- moved
- destroyed

Destroying or replacing a Compute Unit does not inherently mean destroying the Allocation that was using it.

This property is important for future capabilities such as migration, recovery, host maintenance, and resource resizing.

---

## Allocation

An Allocation represents a user's durable claim on Kloigos resources and the logical identity of the workload associated with that claim.

The Allocation exists independently from the particular Compute Unit currently executing it.

An Allocation may own or reference:

- Allocation ID
- organization or owner
- requested resource configuration
- Instance Class
- tenancy policy
- workload metadata
- Unix/login identity
- SSH configuration
- network identity
- persistent storage
- security configuration
- metering history
- lifecycle state
- current Compute Unit placement

Not every resource necessarily has identical persistence semantics, but resources intended to survive CU replacement belong conceptually to the Allocation rather than to the CU.

### Allocation Identity Is Stable

Changes in physical placement should not require the user to receive a new workload identity.

For example:

```text
Before:

Allocation A
IP: 10.20.30.41
Storage: volume-A
        │
        ▼
CU-17
        │
        ▼
Host-3


After placement change:

Allocation A
IP: 10.20.30.41
Storage: volume-A
        │
        ▼
CU-82
        │
        ▼
Host-9
```

The exact ability to preserve a particular resource, such as an IP address across physical network boundaries, depends on the corresponding subsystem design.

The architectural principle is that changing Compute Units does not by itself create a new Allocation.

---

## Why the Separation Exists

Without this distinction, Kloigos would effectively make the physical execution slot the workload identity.

That would tightly couple:

```text
workload identity
        =
Compute Unit
        =
resource configuration
        =
physical placement
```

Operations such as resizing or moving a workload would then require destroying one identity and creating another.

Instead, Kloigos separates them:

```text
Durable Identity               Execution
───────────────               ─────────────

Allocation                     Compute Unit
    │                              │
    │ attached to                  │ created from
    └─────────────────────────────►│
                                   │
                                   ▼
                              Host Capacity
```

This gives the control plane freedom to change execution placement while preserving the user's logical resource.

---

## Relationship to Dynamic Provisioning

Historically, a Kloigos host may contain administrator-created Compute Units with predefined shapes.

The target architecture instead treats the physical host as the owner of allocatable capacity.

When an Allocation requires execution capacity, Kloigos can construct an appropriate Compute Unit from available resources.

Conceptually:

```text
Allocation Request
        │
        ▼
Determine Requirements
        │
        ▼
Select Host
        │
        ▼
Reserve Capacity
        │
        ▼
Materialize Compute Unit
        │
        ▼
Attach Allocation
        │
        ▼
Activate Workload
```

This reinforces the separation between the two abstractions.

The Allocation describes the durable request and identity.

The Compute Unit is the physical realization of that request at a particular point in time.

The complete provisioning model is defined in the **Dynamic Compute Unit Provisioning** design document.

---

## Resource Ownership

A useful architectural rule is:

> **Durable resources belong to the Allocation. Replaceable execution resources belong to the Compute Unit.**

For example:

| Resource or State | Primary Concept |
|---|---|
| Workload identity | Allocation |
| Ownership / organization | Allocation |
| Requested resource shape | Allocation |
| Instance Class | Allocation |
| Tenancy requirement | Allocation |
| Metadata | Allocation |
| Metering history | Allocation |
| Persistent storage identity | Allocation |
| Current placement | Allocation references CU |
| Physical CPU assignment | Compute Unit |
| cgroup hierarchy | Compute Unit |
| memory enforcement | Compute Unit |
| scheduler configuration | Compute Unit |
| host-side network enforcement | Compute Unit |
| host-side security enforcement | Compute Unit |

Some resources cross the boundary.

For example, an IP address may logically belong to an Allocation while its actual interface and nftables configuration are materialized as part of the Compute Unit.

Similarly, persistent storage may belong to the Allocation while its mount and host-side attachment belong to the CU.

This distinction between **logical ownership** and **physical realization** is intentional.

---

## Lifecycle

The Allocation and Compute Unit have related but independent lifecycles.

A simplified Allocation lifecycle may resemble:

```text
REQUESTED
    │
    ▼
SCHEDULING
    │
    ▼
PROVISIONING
    │
    ▼
ACTIVE
    │
    ├── resize / move / reconstruct
    │
    ▼
TERMINATING
    │
    ▼
TERMINATED
```

Compute Units have a shorter execution-oriented lifecycle:

```text
RESERVED
    │
    ▼
MATERIALIZING
    │
    ▼
ACTIVE
    │
    ▼
RELEASING
    │
    ▼
DESTROYED
```

The exact lifecycle state machines may evolve.

The important architectural property is that the lifecycles are not identical.

One Allocation may potentially use multiple Compute Units over its lifetime.

---

## Replacement and Migration

Because Allocation identity is separate from CU placement, Kloigos can eventually support operations such as:

```text
Allocation A
     │
     ▼
CU-1 on Host-A

     │
     │ placement transition
     ▼

Allocation A
     │
     ▼
CU-2 on Host-B
```

A placement transition may require:

1. selecting a destination host
2. reserving destination resources
3. materializing a destination CU
4. making durable Allocation resources available there
5. transitioning workload execution
6. updating current placement
7. releasing the old CU

This architecture does not imply that transparent live process migration is required.

Kloigos may reconstruct or restart workloads as part of a placement transition.

The important property is that **Allocation identity survives CU replacement**.

---

## Failure Semantics

Compute Unit creation may fail after some resources have already been reserved or partially configured.

For example:

```text
CPU reserved
     ↓
Memory reserved
     ↓
IP reserved
     ↓
Storage attached
     ↓
Network configuration FAILED
```

A failed CU provisioning operation must not leave reusable host resources permanently consumed or create a partially active workload environment.

Cleanup must release resources associated with the failed Compute Unit while preserving durable Allocation state where appropriate.

Likewise, failure while destroying a CU must be detectable and recoverable rather than silently marking resources as available while they remain active on the host.

Detailed transactional reservation and cleanup behavior belongs in the **Dynamic Compute Unit Provisioning** design.

---

## Control Plane and Host State

The control plane owns the desired state and lifecycle of Allocations and Compute Units.

The physical host enforces the resulting execution boundaries.

Conceptually:

```text
Control Plane
     │
     │ desired state
     ▼
Compute Unit Configuration
     │
     │ materialized as
     ▼
Linux Host State
```

The control plane must not assume that a database record alone proves successful enforcement.

Validation and reconciliation should be capable of detecting divergence between control-plane state and actual host state.

---

## Architectural Invariants

The Compute Unit and Allocation model is governed by the following invariants:

1. **An Allocation and a Compute Unit are distinct entities.**

2. **An Allocation represents durable workload identity and resource intent.**

3. **A Compute Unit represents the concrete Linux execution boundary for an Allocation.**

4. **A Compute Unit may be replaced without inherently replacing the Allocation.**

5. **Physical placement belongs to the execution layer and may change during an Allocation's lifetime.**

6. **Durable Allocation resources must not be destroyed merely because a Compute Unit is destroyed or replaced.**

7. **Resources promised by a Compute Unit must correspond to real host-enforced boundaries, not only control-plane records.**

8. **Exclusive physical resources assigned to a Compute Unit must not simultaneously be assigned elsewhere in violation of their isolation guarantees.**

9. **Failed Compute Unit provisioning must not leak reusable infrastructure capacity.**

10. **Logical resource ownership and physical resource realization may exist at different layers.**

11. **The control plane must be able to determine which Compute Unit currently realizes an active Allocation.**

12. **Compute Unit implementation details may evolve without changing Allocation identity semantics.**

---

## Related Design Documents

This document defines the boundary between the two central Kloigos abstractions.

Detailed subsystem behavior belongs in the corresponding design documents:

- **Dynamic Compute Unit Provisioning** — host capacity, reservation, CU materialization, teardown, and failure cleanup.
- **CPU Resource Model** — Dedicated and Shared CPU semantics and enforcement.
- **Scheduling and Placement Model** — host selection and multidimensional placement constraints.
- **Networking and IP Model** — IP ownership, assignment, host networking, and network lifecycle.
- **Storage and Persistence Model** — persistent storage ownership, attachment, teardown, and migration.
- **Security and Isolation Model** — security boundaries applied to Compute Units.
- **Tenancy Model** — organization-level physical-host sharing constraints.
- **Metering and Pricing Model** — resource accounting across Allocation lifetime and configuration changes.

The central principle connecting all of these designs remains:

> **Hosts provide capacity. Compute Units provide execution boundaries. Allocations provide durable workload identity.**
