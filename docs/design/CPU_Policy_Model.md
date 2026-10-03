# CPU Policy Model

## Overview

Kloigos uses **CPU Policies** to describe how CPU capacity is delivered to Compute Units.

A CPU Policy is an administrator-defined, reusable resource policy that determines whether CPU capacity is exclusive or shared and, for shared capacity, how much logical CPU capacity may be allocated relative to the underlying physical CPU capacity.

CPU Policies provide a stable abstraction between:

- physical CPU resources;
- host CPU pools;
- Instance Classes;
- scheduling and capacity accounting;
- Compute Unit provisioning.

CPU Policies intentionally describe **resource semantics**, not the exact Linux or systemd mechanism used to enforce those semantics.

The implementation may use cgroups v2, systemd resource controls, CPU affinity, cpusets, CPU weights, CPU bandwidth controls, or other appropriate Linux mechanisms.

Those implementation details may evolve without changing the CPU Policy exposed to the rest of Kloigos.

---

## Goals

The CPU Policy model must:

- support exclusive CPU allocation;
- support shared CPU allocation;
- support administrator-defined CPU overcommit ratios;
- provide deterministic capacity accounting;
- prevent Shared CPU workloads from consuming CPU capacity reserved for Dedicated CPU workloads;
- allow administrators to define reusable CPU policies;
- allow Instance Classes to reference CPU policies;
- support heterogeneous physical hosts;
- integrate with Dynamic Compute Unit Provisioning;
- avoid exposing infrastructure-level CPU overcommit decisions directly to application users.

---

## Core Concepts

The CPU resource model separates four concepts:

```text
Physical CPUs
     │
     ▼
CPU Pools
     │
     │ implement
     ▼
CPU Policies
     │
     │ referenced by
     ▼
Instance Classes
     │
     │ selected by
     ▼
Allocation Requests
```

These concepts must remain distinct.

### Physical CPU

The actual logical processors exposed by Linux on a physical host.

Kloigos discovers CPU topology from the host, including information such as:

- CPU identifiers;
- sockets;
- cores;
- threads;
- NUMA topology.

### CPU Pool

A set of physical CPUs on a host assigned to a particular CPU resource policy.

For example:

```text
64 CPU Host

CPUs 0-31
└── Dedicated Pool

CPUs 32-47
└── Shared Standard Pool

CPUs 48-63
└── Shared Economy Pool
```

CPU pools define where workloads governed by a CPU Policy may execute.

### CPU Policy

An administrator-defined reusable description of how CPU capacity is delivered.

Examples:

```text
dedicated
shared-standard
shared-economy
```

### Instance Class

An administrator-defined user-facing compute product.

An Instance Class combines eligible Host Families with a CPU Policy and other resource characteristics.

For example:

```text
general-purpose
├── Host Families
│   ├── amd-epyc-gen4
│   └── intel-xeon-gen5
└── CPU Policy
    └── shared-standard
```

The application user selects `general-purpose`.

The application user does not need to understand that `shared-standard` may internally represent a 2:1 CPU overcommit policy.

---

## Dedicated CPU Policy

A Dedicated CPU Policy provides exclusive CPU capacity.

Conceptually:

```yaml
cpu_policy:
  name: dedicated
  mode: dedicated
```

For Dedicated CPU:

```text
1 allocated CPU
        =
1 exclusively allocated physical CPU
```

A physical CPU assigned to one Dedicated Compute Unit must not simultaneously be allocated to another Compute Unit.

For example, if a host has 32 CPUs available to a Dedicated CPU pool:

```text
Physical capacity: 32 CPUs
Logical capacity:  32 CPUs
Overcommit:         none
```

An allocation requesting:

```text
16 Dedicated CPUs
```

consumes 16 physical CPUs from that pool.

Another 16-CPU allocation may consume the remaining capacity.

A third allocation requiring Dedicated CPU cannot be placed until sufficient physical capacity becomes available.

Dedicated CPU therefore provides predictable and exclusive CPU ownership.

---

## Shared CPU Policy

A Shared CPU Policy allows multiple Compute Units to execute within the same physical CPU pool.

Conceptually:

```yaml
cpu_policy:
  name: shared-standard
  mode: shared
  overcommit_ratio: 2.0
```

Unlike Dedicated CPU, Shared CPU does not assign exclusive physical CPU ownership to each allocated logical CPU.

Linux schedules runnable workloads across the CPUs belonging to the shared pool.

Shared CPU therefore allows Kloigos to use statistical multiplexing across workloads.

---

## Shared CPU Overcommit

A Shared CPU Policy may define an overcommit ratio.

For example:

```text
1:1
2:1
4:1
```

The ratio determines the logical CPU capacity Kloigos may allocate from a physical Shared CPU pool.

The basic capacity relationship is:

```text
logical CPU capacity =
physical CPUs × overcommit ratio
```

For example, a pool containing:

```text
16 physical CPUs
```

with:

```text
overcommit_ratio = 2.0
```

provides:

```text
32 logical Shared CPUs
```

A pool with:

```text
16 physical CPUs
```

and:

```text
overcommit_ratio = 4.0
```

provides:

```text
64 logical Shared CPUs
```

This is primarily a scheduling and capacity-accounting property.

---

## Shared CPU Without Overcommit

Shared CPU and CPU overcommit are related but are not identical concepts.

A Shared CPU Policy may use:

```text
overcommit_ratio = 1.0
```

In that configuration:

```text
16 physical CPUs
=
16 allocatable logical CPUs
```

However, those CPUs are still scheduler-shared rather than exclusively assigned.

Therefore:

```text
Dedicated 1:1
```

and:

```text
Shared 1:1
```

have different semantics.

Dedicated CPU provides exclusive CPU ownership.

Shared 1:1 CPU provides shared scheduler access while preventing Kloigos from allocating more logical CPU capacity than the physical pool contains.

---

## Administrator-Defined Policies

Kloigos should not require a fixed global set of CPU policies.

Administrators may define policies appropriate for their infrastructure.

For example:

```yaml
cpu_policies:

  dedicated:
    mode: dedicated

  shared-standard:
    mode: shared
    overcommit_ratio: 2.0

  shared-economy:
    mode: shared
    overcommit_ratio: 4.0
```

Another Kloigos deployment might define:

```yaml
cpu_policies:

  dedicated:
    mode: dedicated

  shared:
    mode: shared
    overcommit_ratio: 1.0

  shared-high-density:
    mode: shared
    overcommit_ratio: 3.0
```

Kloigos should not impose particular overcommit ratios as universal product definitions.

The administrator owns that policy.

---

## CPU Policies Are Infrastructure Policy

CPU overcommit should normally not be selected directly by application users.

For example, an Allocation request should generally not expose:

```yaml
cpu:
  overcommit_ratio: 4.0
```

Instead, the administrator packages CPU behavior into an Instance Class.

For example:

```yaml
instance_class:
  name: economical

  eligible_host_families:
    - intel-xeon-legacy
    - amd-epyc-gen2

  cpu_policy: shared-economy
```

The user then requests:

```yaml
instance_class: economical

resources:
  cpu: 8
  memory: 32GiB
```

The Instance Class determines the CPU Policy.

This keeps infrastructure-level scheduling and overcommit decisions under administrator control.

---

## Relationship to Host Families

Host Families and CPU Policies describe different dimensions of infrastructure.

A Host Family answers:

> What kind of hardware can provide this capacity?

A CPU Policy answers:

> How is CPU capacity delivered from that hardware?

For example:

```text
Host Family:
amd-epyc-gen4

CPU Policies available on hosts:
├── dedicated
├── shared-standard
└── shared-economy
```

A Host Family must not itself imply a particular CPU Policy.

The same hardware family may provide multiple CPU resource policies.

---

## Relationship to CPU Pools

CPU Policies describe behavior.

CPU Pools represent physical host resources implementing that behavior.

For example:

```text
Host: server-042
Host Family: amd-epyc-gen4
64 CPUs

CPU Pool A
├── CPUs: 0-31
└── Policy: dedicated

CPU Pool B
├── CPUs: 32-47
└── Policy: shared-standard
    └── overcommit: 2:1

CPU Pool C
├── CPUs: 48-63
└── Policy: shared-economy
    └── overcommit: 4:1
```

The CPU Policy is reusable across hosts.

For example:

```text
shared-standard
       │
       ├── server-001 / CPUs 32-47
       ├── server-002 / CPUs 16-31
       └── server-003 / CPUs 48-63
```

The physical CPU identifiers are therefore properties of each host's CPU pool, not properties of the CPU Policy.

---

## Pool Isolation

CPU pool boundaries must be enforced.

A Compute Unit using a Shared CPU Policy must not execute on CPUs reserved for a Dedicated CPU pool.

For example:

```text
64 CPU Host

CPUs 0-31
Dedicated Pool

CPUs 32-63
Shared Pool
```

Shared workloads must remain within:

```text
CPUs 32-63
```

even when CPUs in the Dedicated pool are idle.

Likewise, Dedicated CPU allocations must not consume CPUs assigned to Shared pools unless the host configuration is explicitly changed by an administrator.

This preserves the semantics and capacity guarantees of each policy.

---

## Capacity Accounting

Kloigos must distinguish between physical CPU capacity and logical allocatable CPU capacity.

For a Dedicated CPU pool:

```text
Physical CPUs:       32
Overcommit ratio:    1:1
Logical capacity:    32
Allocated:           20
Available:           12
```

For a Shared 2:1 pool:

```text
Physical CPUs:       16
Overcommit ratio:    2:1
Logical capacity:    32
Allocated:           20
Available:           12
```

For a Shared 4:1 pool:

```text
Physical CPUs:       16
Overcommit ratio:    4:1
Logical capacity:    64
Allocated:           40
Available:           24
```

Scheduling decisions for Shared CPU must use logical capacity while retaining knowledge of the underlying physical capacity and topology.

---

## Relationship to Dynamic Compute Unit Provisioning

Dynamic Compute Unit Provisioning consumes the CPU Policy selected through the Instance Class.

Conceptually:

```text
Allocation Request
        │
        ▼
Instance Class
        │
        ├── Eligible Host Families
        │
        └── CPU Policy
                │
                ▼
        Candidate Hosts
                │
                ▼
        Compatible CPU Pools
                │
                ▼
        Capacity Evaluation
                │
                ▼
        CPU Reservation
                │
                ▼
        Compute Unit Materialization
```

For Dedicated CPU, reservation consumes exclusive physical CPUs.

For Shared CPU, reservation consumes logical CPU capacity from a compatible Shared CPU pool.

The scheduler must prevent concurrent provisioning operations from allocating the same available capacity more than once.

---

## Burstable Behavior

Shared CPU should permit work-conserving behavior where appropriate.

When physical CPU capacity within a Shared CPU pool is idle, a Compute Unit may be able to consume more CPU time than its nominal entitlement.

Under contention, CPU resources should be distributed according to the semantics defined by the Shared CPU implementation.

For example, an Allocation purchasing:

```text
8 Shared CPUs
```

may represent an entitlement to a proportion of the shared pool rather than ownership of eight specific physical CPUs.

The exact mechanism used to translate logical Shared CPU allocation into runtime scheduler behavior is intentionally not defined by this document.

---

## Linux and systemd Enforcement

CPU Policies define Kloigos semantics rather than a specific Linux implementation.

Kloigos will use standard Linux and systemd resource-control mechanisms to enforce those semantics.

Potential mechanisms include, but are not limited to:

- CPU affinity and CPU sets;
- systemd `AllowedCPUs=`;
- cgroups v2 `cpuset.cpus`;
- systemd `CPUWeight=`;
- cgroups v2 `cpu.weight`;
- systemd CPU quota controls;
- cgroups v2 `cpu.max`;
- other appropriate Linux CPU-controller functionality.

### Implementation Decision Required

The exact mapping between Kloigos Shared CPU semantics and Linux/systemd controls requires further design and validation.

In particular, implementation work must determine:

- how one logical Shared CPU maps to scheduler entitlement;
- whether `CPUWeight` / `cpu.weight` should provide proportional entitlement;
- whether `CPUQuota` / `cpu.max` should impose an upper CPU ceiling;
- whether Shared CPU should be completely work-conserving when unused capacity exists;
- how burst capacity should behave;
- how weights should be calculated for differently sized Compute Units;
- how nested workloads such as Kubernetes interact with the outer CPU controls;
- how CPU controls behave under sustained contention;
- how NUMA topology should influence Shared CPU pool construction;
- how SMT/hyperthreads are represented in physical and logical CPU accounting.

These are implementation-level decisions and must be validated against actual Linux scheduler behavior before Kloigos commits to a specific mechanism.

The CPU Policy abstraction should remain stable even if the underlying enforcement implementation changes.

---

## Example

Consider a physical host with:

```text
Host: server-042
Host Family: amd-epyc-gen4
CPUs: 64
```

The administrator configures:

```text
CPUs 0-31
→ dedicated pool
→ CPU Policy: dedicated

CPUs 32-47
→ standard shared pool
→ CPU Policy: shared-standard
→ overcommit: 2:1

CPUs 48-63
→ economy shared pool
→ CPU Policy: shared-economy
→ overcommit: 4:1
```

Capacity becomes:

```text
Dedicated
32 physical CPUs
32 logical CPUs

Shared Standard
16 physical CPUs
32 logical CPUs

Shared Economy
16 physical CPUs
64 logical CPUs
```

The administrator can then construct Instance Classes such as:

```text
compute-optimized
├── Host Family: amd-epyc-gen4
└── CPU Policy: dedicated

general-purpose
├── Host Family: amd-epyc-gen4
└── CPU Policy: shared-standard

economical
├── Host Family: amd-epyc-gen4
└── CPU Policy: shared-economy
```

Application users consume these products without needing to understand the underlying CPU pool topology or overcommit configuration.

---

## Validation Requirements

The CPU Policy implementation must eventually validate:

### Dedicated CPU

- exclusive CPU assignment;
- no CPU overlap between Dedicated Compute Units;
- no execution outside the assigned CPU set;
- correct capacity accounting;
- correct release of CPU capacity after teardown.

### Shared CPU

- execution remains within the configured Shared CPU pool;
- Shared workloads cannot execute on Dedicated CPUs;
- logical capacity follows the configured overcommit ratio;
- scheduler refuses allocations after logical capacity is exhausted;
- capacity is correctly returned after teardown.

### Contention

Validation must test real workloads under CPU contention.

Tests should verify:

- behavior when the pool is idle;
- behavior when the pool is partially utilized;
- behavior when the pool is fully saturated;
- fairness between similarly sized Compute Units;
- proportional behavior between differently sized Compute Units;
- isolation between Dedicated and Shared pools;
- burst behavior;
- sustained CPU pressure.

These tests should use real workload generators such as `stress-ng` and should form part of the Kloigos validation harness.

---

## Non-Goals

This document does not define:

- the complete Instance Class model;
- Host Family classification;
- pricing for different CPU policies;
- a fixed catalog of CPU policies;
- exact Linux scheduler tuning;
- exact systemd configuration;
- exact `CPUWeight` calculations;
- exact `cpu.max` calculations;
- NUMA scheduling algorithms;
- placement algorithms.

Those concerns either belong to separate design documents or require implementation experimentation.

---

## Architectural Invariants

> **CPU Policies describe how CPU capacity is delivered, not what physical hardware provides it.**

> **Host Families describe hardware classification; CPU Policies describe CPU resource behavior.**

> **CPU Policies are administrator-defined and reusable.**

> **Instance Classes package CPU Policies with eligible Host Families and other resource characteristics.**

> **Application users normally select Instance Classes rather than raw CPU overcommit ratios.**

> **Dedicated CPU capacity is exclusive and must not be overcommitted.**

> **Shared CPU capacity may be logically overcommitted according to administrator policy.**

> **Shared CPU workloads must remain within their configured physical CPU pool.**

> **CPU overcommit affects logical scheduling capacity and must not obscure the underlying physical capacity.**

> **The exact Linux/systemd enforcement mechanism is an implementation detail and may evolve independently of the CPU Policy abstraction.**

---

## Open Implementation Questions

The following questions must be resolved during implementation design and validation:

1. What runtime entitlement does one logical Shared CPU represent?
2. Should proportional sharing primarily use `CPUWeight` / `cpu.weight`?
3. Should Shared CPU have an explicit ceiling using `CPUQuota` / `cpu.max`?
4. How much unused CPU capacity may a Shared Compute Unit burst into?
5. How should weights be calculated from requested logical CPU counts?
6. How should SMT threads be represented for Dedicated and Shared capacity?
7. How should Shared pools interact with NUMA topology?
8. How should nested cgroup delegation behave for Kubernetes running inside a Compute Unit?
9. Should CPU pool membership be statically configured by administrators or support later dynamic resizing?
10. What measurements should the validation harness use to prove that the selected implementation matches the CPU Policy semantics?

These questions should be answered through focused implementation design and empirical testing rather than being encoded prematurely into the CPU Policy abstraction.
