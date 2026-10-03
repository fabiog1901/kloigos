# Dynamic Compute Unit Provisioner

## Overview

The **Dynamic Compute Unit Provisioner** materializes a Compute Unit from the resource assignments already recorded in an Allocation.

```text
Allocation Request
        |
        v
     Allocator
        |
        v
    Allocation
        |
        v
Dynamic CU Provisioner
        |
        v
   Compute Unit
```

The Allocator decides **where** resources come from.

The Provisioner decides **how** those assigned resources become a concrete Linux Compute Unit.

---

## Input

The Provisioner receives an Allocation containing or referencing a complete placement.

Conceptually:

```text
Allocation

Host
Logical CPU Manager
CPU assignment / entitlement
Memory
Storage assignment
IP
Tenancy
...
```

The Provisioner must not repeat placement.

---

## Materialization

The Provisioner translates Allocation state into Host configuration.

This may include:

```text
Allocation
    |
    +-- Unix identity
    +-- systemd
    +-- cgroups
    +-- CPU controls
    +-- memory controls
    +-- filesystem
    +-- LVM/storage
    +-- networking
    +-- nftables
    +-- SSH
    |
    v
Compute Unit
```

The resulting Compute Unit is the concrete Linux resource boundary associated with the Allocation.

---

## CPU

CPU resources come from the Logical CPU Manager selected by the Allocator.

### Dedicated

The Allocation contains specific physical CPUs.

Example:

```text
Logical CPU Manager:
dedicated-1

Physical CPUs:
12-19
```

The Provisioner configures the Compute Unit so execution is restricted to those CPUs.

### Shared

The Allocation contains a logical CPU entitlement and references a Shared Logical CPU Manager.

Example:

```text
Logical CPU Manager:
shared-standard-1

Physical CPU domain:
32-47

Logical entitlement:
8
```

The Provisioner translates this into the appropriate systemd/cgroup configuration according to the Shared/Burstable CPU implementation.

The Provisioner does not select the CPU Policy or Logical CPU Manager.

---

## Memory

The Provisioner enforces the memory quantity assigned to the Allocation.

It does not decide whether sufficient Host memory exists.

That decision has already been made by the Allocator.

---

## Storage

The Provisioner materializes assigned storage.

This may include:

- LVM logical volume creation;
- filesystem preparation;
- mounting;
- ownership and permissions.

Persistent Allocation storage remains independent from Compute Unit lifecycle.

Destroying a Compute Unit must not unintentionally destroy persistent Allocation storage.

---

## Networking

The Provisioner materializes the network assignment selected during allocation.

This may include:

- configuring the assigned IP on the Host;
- associating the IP with the Compute Unit;
- nftables enforcement;
- network security rules.

The Provisioner does not select an IP address.

---

## Lifecycle

Conceptually:

```text
ALLOCATED
    |
    v
PROVISIONING
    |
    v
ACTIVE
```

If provisioning fails, the Compute Unit must not appear ACTIVE.

Partial Host-side state should be cleaned up where possible and the failure recorded for diagnosis.

---

## Teardown

Compute Unit teardown removes Host-side materialization.

This may include:

```text
systemd / cgroups
temporary filesystem state
network configuration
nftables state
temporary storage
Unix identity
```

Durable Allocation resources follow their own lifecycle.

---

## Failure Boundary

Provisioning may fail after a valid placement has already been committed.

The Provisioner is responsible for handling and reporting failures during Host materialization.

It must not silently choose another Host or Logical CPU Manager.

If the placement must change, control returns to the Allocator.

---

## Relationship to Allocation

The Allocation is durable.

The Compute Unit is its current physical realization.

This allows Kloigos to preserve workload identity independently from a particular Compute Unit or Host placement.

```text
Allocation
   |
   +---- current placement
   |
   v
Compute Unit
```

A future replacement or migration may produce a different Compute Unit while preserving the Allocation identity.

---

## Design Invariants

> The Provisioner materializes resources already selected by the Allocator.

> The Provisioner does not perform placement.

> The Allocation is the durable input to provisioning.

> The Compute Unit is the concrete Linux realization of an Allocation.

> CPU configuration follows the Logical CPU Manager and CPU assignment recorded in the Allocation.

> The Provisioner does not independently select CPU Policy, Host, IP, or resource capacity.

> Provisioning failures must not silently change placement.

> A failed provisioning attempt must not produce an ACTIVE Compute Unit.

> Compute Unit teardown must not unintentionally destroy durable Allocation resources.

> Re-placement always returns through the Allocator.
