# Logical CPU Manager

## Overview

Kloigos uses **Logical CPU Managers** to mediate between the physical CPU resources of a Host and the CPU resources assigned to Allocations.

An Allocation does not consume CPUs directly from a Host.

Instead:

> **An Allocation obtains CPU capacity from a Logical CPU Manager belonging to that Host.**

A Logical CPU Manager owns a defined subset of a Host's physical CPUs, implements one CPU Policy, tracks CPU assignments, and exposes allocatable CPU capacity to the Kloigos allocator.

This creates a resource-management layer between physical hardware and Compute Units.

Conceptually:

```text
Host
 │
 │ owns physical CPUs
 ▼
Logical CPU Manager
 │
 │ manages and allocates CPU capacity
 ▼
Allocation
 │
 ▼
Compute Unit
```

This is analogous to the role that a logical volume manager plays between physical storage and logical storage allocations:

```text
STORAGE                         CPU

Physical Storage                Physical CPUs
       │                              │
       ▼                              ▼
Logical Volume Manager          Logical CPU Manager
       │                              │
       ▼                              ▼
Logical Volume                  CPU Allocation
       │                              │
       └──────────► Compute Unit ◄────┘
```

The Logical CPU Manager is a Kloigos control-plane abstraction and is persisted as part of the authoritative infrastructure state.

It is not necessarily a separate daemon or host-local service.

---

## Goals

The Logical CPU Manager model must:

- provide an explicit boundary between physical Host CPUs and Allocation CPU resources;
- support multiple CPU Policies on the same Host;
- support Dedicated CPU assignment;
- support Shared CPU capacity;
- maintain authoritative CPU assignment state;
- expose capacity information to the allocator;
- allow fleet-wide placement decisions using control-plane database state;
- prevent physical CPUs from being assigned to incompatible CPU managers simultaneously;
- support future topology-aware CPU placement;
- remain independent from the exact Linux/systemd CPU enforcement mechanism.

---

## Core Resource Hierarchy

The CPU resource hierarchy is:

```text
Host
 │
 │ owns
 ▼
Physical CPUs
 │
 │ partitioned among
 ▼
Logical CPU Managers
 │
 │ governed by
 ▼
CPU Policies
 │
 │ provide CPU capacity to
 ▼
Allocations
 │
 │ materialized as
 ▼
Compute Units
```

Each layer has a distinct responsibility.

### Host

The Host owns the physical CPU hardware.

### Logical CPU Manager

The Logical CPU Manager owns and manages a subset of the Host's physical CPUs.

### CPU Policy

The CPU Policy defines how the Logical CPU Manager delivers CPU capacity.

### Allocation

The Allocation consumes CPU capacity from a Logical CPU Manager.

### Compute Unit

The Compute Unit implements the CPU assignment on the physical Host using the appropriate Linux resource-control mechanisms.

---

## Multiple Logical CPU Managers per Host

A Host may contain multiple Logical CPU Managers.

This allows different subsets of the Host's physical CPUs to implement different CPU Policies.

For example:

```text
Host: server-42
Physical CPUs: 0-63

├── Logical CPU Manager A
│   Policy: dedicated
│   Physical CPUs: 0-31
│
└── Logical CPU Manager B
    Policy: shared-standard
    Physical CPUs: 32-63
```

The same Host therefore simultaneously provides:

```text
Dedicated CPU capacity
```

and:

```text
Shared CPU capacity
```

without mixing the underlying physical CPU resources.

---

## Multiple Shared Policies

A Host may also provide multiple Shared CPU policies.

For example:

```text
Host: server-42
Physical CPUs: 0-63

├── Logical CPU Manager A
│   Policy: dedicated
│   CPUs: 0-15
│
├── Logical CPU Manager B
│   Policy: shared-standard
│   Overcommit: 2:1
│   CPUs: 16-47
│
└── Logical CPU Manager C
    Policy: shared-economy
    Overcommit: 4:1
    CPUs: 48-63
```

Each Logical CPU Manager remains independently accountable for its CPU capacity.

---

## Physical CPU Ownership

Every Logical CPU Manager owns a defined set of physical CPUs from its Host.

For example:

```text
Logical CPU Manager

Host:
server-42

Physical CPUs:
16-47

CPU Policy:
shared-standard
```

Physical CPU membership is authoritative configuration.

A physical CPU must not simultaneously belong to multiple Logical CPU Managers.

For example, this is invalid:

```text
Manager A
CPUs: 0-31

Manager B
CPUs: 16-47
```

because CPUs `16-31` overlap.

Kloigos must reject such configuration.

---

## Host-Reserved CPUs

Not every physical CPU on a Host is required to belong to a Logical CPU Manager.

For example:

```text
Host CPUs: 0-63

0-3
└── Host / Kloigos reserved

4-31
└── Logical CPU Manager: dedicated

32-63
└── Logical CPU Manager: shared-standard
```

This allows administrators to reserve CPU resources for:

- the Host operating system;
- Kloigos host services;
- infrastructure agents;
- operational overhead;
- future capacity;
- other administrator-defined purposes.

Therefore:

> The union of Logical CPU Manager CPU sets does not need to equal the complete physical CPU set of the Host.

---

## CPU Policy Relationship

Every Logical CPU Manager implements exactly one CPU Policy.

For example:

```text
Logical CPU Manager
        │
        └── CPU Policy: dedicated
```

or:

```text
Logical CPU Manager
        │
        └── CPU Policy: shared-standard
```

The CPU Policy defines the resource semantics.

The Logical CPU Manager applies those semantics to actual physical CPUs on a specific Host.

The distinction is:

```text
CPU Policy
"What does Shared Standard mean?"

Logical CPU Manager
"Which physical CPUs on this Host implement Shared Standard?"
```

CPU Policies are reusable across Hosts.

Logical CPU Managers are Host-specific.

---

## Dedicated Logical CPU Manager

A Logical CPU Manager using a Dedicated CPU Policy provides exclusive physical CPU assignment.

For example:

```text
Logical CPU Manager: dedicated-1

Physical CPUs:
0-15

Policy:
dedicated
```

Allocations might be:

```text
Allocation A
CPUs: 0-3

Allocation B
CPUs: 4-11

Available:
CPUs 12-15
```

For Dedicated CPU, the Logical CPU Manager must maintain both:

- the amount of CPU capacity allocated;
- the specific physical CPUs assigned to each Allocation.

Capacity alone is insufficient.

For example:

```text
Total CPUs:       16
Allocated CPUs:   12
Available CPUs:    4
```

must ultimately correspond to actual CPU assignments such as:

```text
Allocated:
0-11

Available:
12-15
```

The exact algorithm used to select individual CPUs may later account for:

- NUMA topology;
- physical cores;
- SMT siblings;
- socket topology;
- cache topology;
- other hardware characteristics.

Those placement algorithms are outside the scope of this document.

---

## Shared Logical CPU Manager

A Logical CPU Manager using a Shared CPU Policy provides logical CPU capacity backed by a physical CPU set.

For example:

```text
Logical CPU Manager: shared-standard-1

Physical CPUs:
32-47

Physical CPU count:
16

Policy:
shared-standard

Overcommit ratio:
2:1
```

This produces:

```text
Physical CPU capacity: 16

Logical CPU capacity:
16 × 2 = 32
```

Allocations might consume:

```text
Allocation A: 8 logical CPUs
Allocation B: 4 logical CPUs
Allocation C: 8 logical CPUs

Total allocated:
20 logical CPUs

Available:
12 logical CPUs
```

Unlike Dedicated CPU, those Allocations do not necessarily own particular physical CPUs.

Instead, they receive logical CPU entitlement backed by the physical CPUs owned by the Logical CPU Manager.

The exact Linux scheduler controls used to implement this entitlement are defined separately.

---

## Capacity

A Logical CPU Manager exposes allocatable CPU capacity.

For Dedicated CPU:

```text
logical capacity = allocatable physical CPUs
```

For example:

```text
Physical CPUs:       32
Logical capacity:    32
```

For Shared CPU:

```text
logical capacity =
physical CPU count × CPU Policy overcommit ratio
```

For example:

```text
Physical CPUs:       16
Overcommit ratio:    2:1

Logical capacity:    32
```

The CPU Policy determines the capacity semantics.

The Logical CPU Manager applies them to its physical CPU set.

---

## Available Capacity

Available CPU capacity is derived from:

```text
Logical CPU Manager capacity
-
CPU capacity consumed by active Allocations
=
Available CPU capacity
```

For example:

```text
Logical capacity:    32

Allocations:
A                     8
B                     4
C                     8
                     ──
Allocated:            20

Available:            12
```

Available capacity does not need to exist as an independent source of truth.

It may be calculated by the control-plane database from authoritative Logical CPU Manager and Allocation state.

Implementation may introduce derived or cached values for performance if necessary, but they must not become inconsistent authoritative state.

---

## Allocation Relationship

An Allocation obtains CPU resources from a Logical CPU Manager.

Conceptually:

```text
Host
 1
 │
 N
Logical CPU Manager
 1
 │
 N
Allocation
```

An Allocation therefore records which Logical CPU Manager provides its CPU capacity.

For example:

```text
Allocation: allocation-123

Host:
server-42

Logical CPU Manager:
shared-standard-1

Requested CPU:
8
```

The Host relationship follows from the Logical CPU Manager because every Logical CPU Manager belongs to exactly one Host.

---

## Dedicated CPU Assignment

For Dedicated CPU, the Allocation must additionally retain the physical CPU assignment.

For example:

```text
Allocation: allocation-123

Logical CPU Manager:
dedicated-1

CPU count:
8

Physical CPUs:
8-15
```

This allows Kloigos to determine exactly which physical CPUs remain available for subsequent Dedicated CPU allocations.

---

## Shared CPU Assignment

For Shared CPU, the Allocation primarily consumes logical CPU capacity.

For example:

```text
Allocation: allocation-456

Logical CPU Manager:
shared-standard-1

Logical CPU count:
8
```

The Allocation executes within the physical CPU set owned by that Logical CPU Manager but does not necessarily own eight specific physical CPUs.

---

## Allocator Relationship

The Dynamic Compute Unit Allocator uses Logical CPU Managers as the CPU-side placement target.

Consider a user request:

```text
Instance Class:
general-purpose

CPU:
8
```

The Instance Class resolves to:

```text
Eligible Host Families:
- amd-epyc-gen4
- intel-xeon-gen5

CPU Policy:
shared-standard
```

The allocator searches control-plane state for Logical CPU Managers satisfying:

```text
Logical CPU Manager CPU Policy
=
shared-standard

AND

Logical CPU Manager Host Family
IN
amd-epyc-gen4,
intel-xeon-gen5

AND

available logical CPU
>=
8
```

Additional placement constraints are evaluated through the associated Host.

For example:

```text
memory capacity
storage capacity
IP availability
tenancy compatibility
host state
other placement constraints
```

The allocator therefore does not need to query Hosts individually.

It operates against authoritative fleet metadata stored by the Kloigos control plane.

---

## Placement Flow

Conceptually:

```text
User
 │
 │ requests
 ▼
Instance Class + CPU Quantity
 │
 ▼
Resolve Instance Class
 │
 ├── Eligible Host Families
 └── Required CPU Policy
 │
 ▼
Query Logical CPU Managers
 │
 ├── correct CPU Policy?
 ├── Host belongs to eligible Host Family?
 ├── sufficient CPU capacity?
 └── Host satisfies remaining constraints?
 │
 ▼
Select Logical CPU Manager
 │
 ├── identifies CPU resource source
 └── identifies Host
 │
 ▼
Create Allocation
 │
 ▼
Materialize Compute Unit
```

Selecting a Logical CPU Manager therefore contributes directly to selecting the Host.

---

## Persistence Model

The exact database schema is an implementation detail, but conceptually the control plane requires persistent state equivalent to:

```text
logical_cpu_managers

id
host_id
cpu_policy_id
physical_cpu_set
enabled
```

Additional derived information may include:

```text
physical_cpu_count
logical_capacity
```

CPU Policy information remains in the CPU Policy model.

Allocation CPU consumption remains associated with the Allocation.

For Dedicated CPU, specific physical CPU assignments must also be persisted.

---

## Conceptual Relationships

```text
HOST
│
│ 1:N
▼
LOGICAL CPU MANAGER
│
├──────────────► CPU POLICY
│
│ 1:N
▼
ALLOCATION
│
▼
COMPUTE UNIT
```

An alternative view is:

```text
Physical Infrastructure

Host
 │
 ├── Physical CPUs
 │
 ├── Logical CPU Manager A
 │      ├── CPU Policy: dedicated
 │      ├── CPUs: 4-31
 │      └── Allocations
 │
 ├── Logical CPU Manager B
 │      ├── CPU Policy: shared-standard
 │      ├── CPUs: 32-63
 │      └── Allocations
 │
 └── Host-reserved CPUs: 0-3
```

---

## Configuration Example

Consider:

```text
Host:
server-42

Host Family:
amd-epyc-gen4

Physical CPUs:
0-63
```

The administrator configures:

```text
CPUs 0-3
Host reserved

CPUs 4-31
Logical CPU Manager:
dedicated

CPUs 32-47
Logical CPU Manager:
shared-standard

CPUs 48-63
Logical CPU Manager:
shared-economy
```

With CPU Policies:

```text
dedicated
mode: dedicated

shared-standard
mode: shared
overcommit: 2:1

shared-economy
mode: shared
overcommit: 4:1
```

The resulting capacity is:

```text
Logical CPU Manager: dedicated

Physical CPUs:
28

Logical CPUs:
28
```

```text
Logical CPU Manager: shared-standard

Physical CPUs:
16

Logical CPUs:
32
```

```text
Logical CPU Manager: shared-economy

Physical CPUs:
16

Logical CPUs:
64
```

The Host therefore exposes three independently managed CPU capacity domains to the allocator.

---

## Relationship to Instance Classes

Instance Classes do not reference individual Logical CPU Managers.

Instead, an Instance Class references:

- eligible Host Families;
- a CPU Policy.

For example:

```text
Instance Class:
general-purpose

Eligible Host Families:
- amd-epyc-gen4
- intel-xeon-gen5

CPU Policy:
shared-standard
```

At runtime, the allocator discovers Logical CPU Managers that satisfy those requirements and have sufficient available capacity.

This prevents Instance Classes from becoming coupled to individual Hosts.

---

## Relationship to Host Families

Host Families classify hardware.

Logical CPU Managers manage CPU resources on individual Hosts.

For example:

```text
Host Family:
amd-epyc-gen4

Hosts:
├── server-01
│   ├── dedicated manager
│   └── shared-standard manager
│
├── server-02
│   └── shared-standard manager
│
└── server-03
    ├── dedicated manager
    ├── shared-standard manager
    └── shared-economy manager
```

Hosts in the same Host Family do not need identical Logical CPU Manager configurations.

Host Family describes hardware compatibility.

Logical CPU Manager configuration describes how each Host's CPU capacity is made available to Kloigos.

---

## Lifecycle

A Logical CPU Manager has an administrator-controlled lifecycle.

Conceptually:

```text
Create
  │
  ▼
Configure physical CPU membership
  │
  ▼
Associate CPU Policy
  │
  ▼
Enable
  │
  ▼
Allocator may consume capacity
  │
  ▼
Disable / Drain
  │
  ▼
No new Allocations
  │
  ▼
Existing Allocations removed
  │
  ▼
Reconfigure or Delete
```

Exact lifecycle states and APIs are implementation details.

However, Kloigos must prevent destructive reconfiguration that would invalidate active CPU assignments.

---

## Reconfiguration

Changing the physical CPU membership of a Logical CPU Manager must account for active Allocations.

For example, Kloigos must not allow:

```text
Manager owns CPUs:
0-31

Allocation A owns:
24-31

Administrator changes manager to:
0-23
```

without first handling Allocation A.

Likewise, changing CPU Policy may alter the meaning or capacity of existing Allocations.

Policy changes therefore require controlled validation and may require draining the Logical CPU Manager before modification.

The exact lifecycle behavior should be defined during implementation.

---

## Validation Requirements

Validation must eventually cover:

### Configuration

- create a Logical CPU Manager;
- associate it with a Host;
- associate it with a CPU Policy;
- assign physical CPUs;
- reject CPUs not belonging to the Host;
- reject overlapping physical CPU membership;
- allow Host CPUs to remain unassigned;
- allow multiple Logical CPU Managers on one Host.

### Dedicated CPU

- allocate specific physical CPUs;
- prevent duplicate physical CPU assignment;
- release physical CPUs when an Allocation ends;
- correctly calculate available capacity;
- ensure Compute Units execute only on assigned CPUs.

### Shared CPU

- calculate logical capacity from physical capacity and CPU Policy;
- allocate logical CPU units;
- reject requests exceeding logical capacity;
- return logical capacity when an Allocation ends;
- prevent workloads from executing outside the manager's physical CPU set.

### Allocator

- filter by CPU Policy;
- filter by Host Family through the associated Host;
- filter by available CPU capacity;
- correctly select among multiple Logical CPU Managers;
- correctly handle multiple managers on the same Host;
- correctly handle exhausted managers;
- correctly ignore disabled or unavailable managers.

---

## Linux and systemd Enforcement

The Logical CPU Manager defines the control-plane CPU resource model.

It does not define the exact Linux implementation.

Potential enforcement mechanisms include:

- CPU affinity;
- cpusets;
- cgroups v2;
- systemd `AllowedCPUs=`;
- systemd `CPUWeight=`;
- systemd CPU quota controls;
- `cpu.weight`;
- `cpu.max`;
- `cpuset.cpus`;
- other appropriate Linux CPU-controller functionality.

The exact implementation must be determined through implementation design and empirical validation.

In particular, Shared CPU semantics still require decisions regarding:

- proportional entitlement;
- burst behavior;
- CPU weight calculation;
- CPU ceilings;
- contention behavior;
- nested cgroup behavior.

Those decisions must not alter the fundamental Logical CPU Manager abstraction.

---

## Non-Goals

This document does not define:

- the complete CPU Policy model;
- the exact Linux/systemd CPU implementation;
- NUMA-aware placement algorithms;
- SMT allocation policy;
- CPU benchmarking;
- Host Family classification;
- Instance Class product design;
- general scheduler ranking;
- memory allocation;
- storage allocation;
- IP allocation;
- pricing.

Those concerns are handled by separate Kloigos components and design documents.

---

## Architectural Invariants

> **Allocations do not consume CPU resources directly from Hosts.**

> **Allocations obtain CPU capacity from Logical CPU Managers.**

> **A Host may contain one or more Logical CPU Managers.**

> **Every Logical CPU Manager belongs to exactly one Host.**

> **Every Logical CPU Manager owns a defined subset of physical CPUs from that Host.**

> **A physical CPU may belong to at most one Logical CPU Manager at a time.**

> **Not every physical CPU on a Host must belong to a Logical CPU Manager.**

> **Every Logical CPU Manager implements exactly one CPU Policy.**

> **Multiple Logical CPU Managers on the same Host may implement different CPU Policies.**

> **Multiple Logical CPU Managers on the same Host may implement the same CPU Policy when administrators require separate CPU resource domains.**

> **Dedicated Logical CPU Managers maintain specific physical CPU assignments for Allocations.**

> **Shared Logical CPU Managers maintain logical CPU capacity and entitlement backed by their physical CPU set.**

> **The Logical CPU Manager is the authoritative control-plane boundary between physical Host CPU resources and Allocation CPU resources.**

> **Instance Classes reference CPU Policies and Host Families, not individual Logical CPU Managers.**

> **The allocator selects compatible Logical CPU Managers using authoritative control-plane database state rather than interrogating Hosts individually.**

> **The exact Linux enforcement mechanism is an implementation detail and may evolve independently of the Logical CPU Manager abstraction.**
