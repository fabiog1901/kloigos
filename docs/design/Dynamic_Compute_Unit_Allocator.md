# Dynamic Compute Unit Allocator

## Overview

The **Dynamic Compute Unit Allocator** determines where the resources required by an Allocation come from.

It performs placement using authoritative Kloigos control-plane state.

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
```

The Allocator decides **where** resources come from.

The Dynamic CU Provisioner decides **how** those resources are materialized on the Host.

---

## Input

A request is expressed using user-facing abstractions.

Example:

```yaml
instance_class: general-purpose

resources:
  cpu: 8
  memory: 32GiB
  storage: 100GiB
```

The Instance Class resolves to infrastructure requirements such as:

```text
Eligible Host Families
CPU Policy
```

---

## Placement

For CPU placement, the Allocator searches **Logical CPU Managers**, not raw Host CPU capacity.

```text
Instance Class
      |
      +-- Eligible Host Families
      +-- CPU Policy
      |
      v
Compatible Logical CPU Managers
      |
      v
Associated Hosts
      |
      +-- memory
      +-- storage
      +-- IP availability
      +-- tenancy
      +-- Host state
      +-- other constraints
      |
      v
Placement
```

Selecting a Logical CPU Manager also identifies the Host.

---

## Dedicated CPU

For Dedicated CPU, the selected Logical CPU Manager assigns specific physical CPUs.

Example:

```text
Logical CPU Manager:
dedicated-1

Assigned CPUs:
12-19
```

Those CPUs become part of the Allocation and cannot simultaneously belong to another active Dedicated Allocation.

---

## Shared CPU

For Shared CPU, the selected Logical CPU Manager provides logical CPU capacity.

Example:

```text
Physical CPUs:
16

CPU Policy:
shared-standard

Logical capacity:
32

Available:
12

Request:
8
```

The Allocation consumes eight logical CPU units.

Linux CPU weights, quotas, and other enforcement details are not Allocator responsibilities.

---

## Other Resources

The selected Host must also satisfy the Allocation's remaining constraints.

These may include:

- memory;
- storage;
- IP availability;
- tenancy;
- accelerators;
- Host lifecycle state.

Not every resource requires the same intermediate abstraction as CPU.

The Allocator evaluates each resource according to its own resource model.

---

## Authoritative State

Placement uses control-plane database state.

The Allocator must not interrogate every Host during placement to discover current capacity.

Relevant state includes:

```text
Instance Classes
Host Families
CPU Policies
Logical CPU Managers
Hosts
Allocations
IP pools
storage state
tenancy state
```

Available capacity should normally be derived from authoritative capacity and active Allocation state rather than independently maintained availability counters.

---

## Transaction Model

Placement occurs within Kloigos' database transaction model.

Serializable transactions protect concurrent placement decisions.

A successful transaction records a complete placement.

A failed transaction must not leave a partial Allocation.

A separate generic reservation or distributed locking subsystem is not required unless future implementation constraints demonstrate a need for one.

---

## Allocation as Placement Record

The Allocation is the durable record of the Allocator's decision.

Conceptually:

```text
Allocation

Instance Class
Host
Logical CPU Manager
CPU quantity
Physical CPU assignment   # Dedicated
Memory
Storage assignment
IP
Tenancy
...
```

The exact database representation may use related tables.

The important requirement is that the Allocation contains enough information for provisioning without another placement decision.

---

## Output

The Allocator produces a complete placement.

Example:

```text
Host:
server-42

Logical CPU Manager:
shared-standard-1

CPU:
8 logical CPUs

Memory:
32 GiB

Storage:
100 GiB

IP:
10.0.10.42
```

The Dynamic CU Provisioner consumes this assignment.

---

## Candidate Selection

Initial placement should remain simple and deterministic.

Advanced strategies such as:

- best-fit;
- spread;
- consolidation;
- NUMA-aware placement;
- topology-aware placement;

may be added later without changing the Allocator/Provisioner boundary.

---

## Failure Boundary

The Allocator owns placement failures.

The Provisioner owns failures encountered while materializing a committed placement.

The Provisioner must not silently select another Host or Logical CPU Manager.

If re-placement is required, control returns to the Allocator.

---

## Design Invariants

> The Allocator decides where resources come from.

> CPU resources are allocated through Logical CPU Managers.

> Selecting a Logical CPU Manager identifies the Host.

> Instance Classes provide Host Family and CPU Policy constraints.

> All placement constraints must be satisfied before placement is committed.

> Placement uses authoritative control-plane database state.

> Hosts are not interrogated during placement to discover current capacity.

> Serializable database transactions protect concurrent allocation decisions.

> The Allocation is the durable record of placement.

> A completed Allocation contains enough information for provisioning without another placement decision.

> The Allocator does not perform Host-side provisioning.
