# Shared and Burstable CPU

## Overview

Kloigos supports CPU capacity that may be shared between multiple Compute Units.

Shared CPU allows multiple Allocations to consume logical CPU capacity backed by the same physical CPU resources.

When unused physical CPU capacity exists, a Compute Unit may be allowed to consume more CPU time than its nominal entitlement. This behavior is referred to as **bursting**.

The purpose of Shared/Burstable CPU is to improve physical CPU utilization while preserving predictable proportional behavior when CPU resources become contended.

Shared/Burstable CPU is implemented through the existing Kloigos CPU abstractions:

```text
Host
  │
  ▼
Logical CPU Manager
  │
  ├── Physical CPU Set
  └── CPU Policy
          │
          ▼
      Shared CPU
          │
          ▼
      Allocations
          │
          ▼
      Compute Units
```

This document defines the semantics of Shared/Burstable CPU.

The exact Linux/systemd/cgroup configuration used to enforce those semantics is an implementation decision that must be validated separately.

---

## Goals

Shared/Burstable CPU must:

- allow multiple Allocations to share physical CPU resources;
- support administrator-defined CPU overcommit;
- expose logical CPU capacity to the allocator;
- provide proportional CPU entitlement during contention;
- allow unused physical CPU capacity to be consumed when possible;
- prevent a Compute Unit from executing outside the physical CPU domain owned by its Logical CPU Manager;
- integrate with CPU Policies, Logical CPU Managers, Instance Classes, and Dynamic Compute Unit provisioning;
- remain understandable to users without exposing low-level scheduler configuration.

---

## Terminology

### Physical CPU Capacity

The CPU resources physically assigned to a Logical CPU Manager.

Example:

```text
Physical CPUs:
32-47

Physical CPU count:
16
```

### Logical CPU Capacity

The amount of allocatable CPU capacity exposed by the Logical CPU Manager.

For Shared CPU:

```text
logical capacity =
physical CPU capacity × overcommit ratio
```

Example:

```text
Physical CPUs:       16
Overcommit ratio:    2:1

Logical CPUs:        32
```

### CPU Entitlement

The relative CPU capacity purchased or assigned to an Allocation.

For example:

```text
Allocation A: 4 CPUs
Allocation B: 8 CPUs
```

Allocation B has twice the CPU entitlement of Allocation A.

### Bursting

Bursting means allowing an Allocation to consume CPU capacity beyond its nominal proportional entitlement when physical CPU capacity would otherwise remain unused.

Bursting does not create additional physical CPU capacity.

---

## CPU Policy

Shared CPU behavior is defined by a CPU Policy.

Conceptually:

```yaml
cpu_policies:
  shared-standard:
    mode: shared
    overcommit_ratio: 2.0

  shared-economy:
    mode: shared
    overcommit_ratio: 4.0
```

The CPU Policy defines the logical capacity represented by physical CPU resources.

The exact Linux scheduler configuration derived from that policy is implementation-specific.

---

## Logical CPU Manager

Shared CPU capacity exists within a Logical CPU Manager.

Example:

```text
Logical CPU Manager

Physical CPUs:
32-47

Physical CPU count:
16

CPU Policy:
shared-standard

Overcommit:
2:1

Logical CPU capacity:
32
```

All Compute Units receiving CPU capacity from this manager execute within the manager's physical CPU domain.

They share those CPUs according to their CPU entitlement.

---

## Allocation Example

Consider:

```text
Physical CPUs:
16

Logical capacity:
32

Overcommit:
2:1
```

Three Allocations consume:

```text
Allocation A:
8 logical CPUs

Allocation B:
8 logical CPUs

Allocation C:
16 logical CPUs
```

Total:

```text
32 logical CPUs
```

The Logical CPU Manager is fully allocated.

The logical CPU quantities represent relative entitlement under contention.

Therefore:

```text
A : B : C
=
8 : 8 : 16
=
1 : 1 : 2
```

When all three Allocations are continuously CPU-bound, Allocation C should receive approximately twice the CPU service of either A or B over an appropriate measurement interval.

Exact short-term scheduling behavior is controlled by Linux and is not expected to be perfectly deterministic.

---

## Contention Semantics

The primary guarantee of Shared CPU is proportional entitlement under sustained contention.

Consider:

```text
A = 4 logical CPUs
B = 8 logical CPUs
```

If both workloads are CPU-bound within the same Logical CPU Manager, their expected relative CPU service is approximately:

```text
A : B
=
1 : 2
```

The implementation should preserve this proportional relationship as closely as practical using standard Linux CPU scheduling controls.

Shared CPU is therefore not equivalent to:

```text
"8 dedicated physical CPUs"
```

Instead it means:

> The Allocation owns eight units of logical CPU entitlement within a shared CPU scheduling domain.

---

## Bursting Semantics

Shared CPU should be work-conserving.

If CPU capacity is idle, active Compute Units should generally be allowed to use it rather than leaving physical CPUs unused solely because their nominal proportional entitlement has been reached.

Example:

```text
Allocation A:
8 logical CPUs

Allocation B:
8 logical CPUs
```

If Allocation B is idle, Allocation A may consume additional available physical CPU capacity.

When Allocation B becomes active, CPU scheduling should converge toward the proportional entitlement of both Allocations.

Therefore:

> CPU entitlement determines behavior during contention, not necessarily a permanent hard execution ceiling.

This is the defining characteristic of Burstable CPU.

---

## Burst Ceiling

Whether Shared/Burstable CPU requires an explicit maximum burst ceiling remains an implementation decision.

Possible models include:

### Uncapped Bursting

An active Compute Unit may consume all currently unused CPU capacity within its Logical CPU Manager.

### Capped Bursting

A Compute Unit may burst only to some configured maximum.

For example:

```text
Entitlement:
4 CPUs

Maximum burst:
8 CPUs
```

The initial implementation should prefer the simplest Linux-native behavior that satisfies the required proportional contention semantics.

A configurable burst ceiling should not be introduced until there is a demonstrated product or operational requirement.

---

## Overcommit

Overcommit determines how much logical CPU capacity can be allocated from a physical CPU domain.

For example:

```text
Physical CPUs:
16
```

With:

```text
1:1
```

the manager exposes:

```text
16 logical CPUs
```

With:

```text
2:1
```

the manager exposes:

```text
32 logical CPUs
```

With:

```text
4:1
```

the manager exposes:

```text
64 logical CPUs
```

Overcommit affects admission control.

It does not alter the amount of physical CPU capacity available.

---

## Shared 1:1 vs Dedicated

Shared CPU with a 1:1 overcommit ratio remains different from Dedicated CPU.

Consider:

```text
16 physical CPUs
16 logical CPUs
```

Under Shared 1:1:

- Allocations share a scheduler domain;
- CPU resources remain work-conserving;
- idle capacity may be consumed by other Allocations;
- Allocations do not own specific physical CPUs.

Under Dedicated CPU:

- physical CPUs are explicitly assigned;
- those CPUs are unavailable to other Allocations;
- CPU ownership is exclusive.

Therefore:

```text
Shared 1:1 != Dedicated
```

The distinction is resource ownership, not merely capacity arithmetic.

---

## Instance Classes

Users should not normally select overcommit ratios directly.

Administrators expose Shared CPU behavior through Instance Classes.

Example:

```yaml
instance_classes:
  general-purpose:
    eligible_host_families:
      - amd-epyc-gen4
      - intel-xeon-gen5
    cpu_policy: shared-standard

  economical:
    eligible_host_families:
      - intel-xeon-legacy
    cpu_policy: shared-economy
```

A user requests:

```text
Instance Class:
general-purpose

CPU:
8
```

The Instance Class determines the CPU Policy.

The user does not need to understand that the underlying infrastructure may use a 2:1 overcommit ratio.

---

## Allocator Behavior

The allocator resolves:

```text
Instance Class
      │
      ├── Eligible Host Families
      └── CPU Policy
              │
              ▼
Compatible Logical CPU Managers
```

For an 8 CPU request, a candidate Shared Logical CPU Manager must have:

```text
available logical CPU capacity >= 8
```

The allocator evaluates logical capacity rather than requiring eight unused physical CPUs.

Example:

```text
Physical CPUs:
16

Policy:
2:1

Logical capacity:
32

Allocated:
24

Available:
8
```

An 8 CPU request may therefore be admitted.

---

## Dynamic Compute Unit Provisioning

After placement, Dynamic Compute Unit provisioning receives:

- selected Host;
- selected Logical CPU Manager;
- requested logical CPU entitlement;
- CPU Policy;
- manager physical CPU set.

Provisioning translates this control-plane state into Linux CPU controls for the Compute Unit.

Conceptually:

```text
Allocation

Logical CPUs:
8

Logical CPU Manager:
shared-standard-1

Physical CPU domain:
32-47
```

becomes:

```text
Compute Unit

Allowed physical CPU domain:
32-47

Relative CPU entitlement:
8 logical CPU units
```

The exact Linux configuration is implementation-specific.

---

## Linux Enforcement

Kloigos should implement Shared/Burstable CPU using standard Linux and systemd/cgroups v2 primitives.

Potential mechanisms include:

```text
systemd:
AllowedCPUs=
CPUWeight=
CPUQuota=

cgroups v2:
cpuset.cpus
cpu.weight
cpu.max
```

The likely conceptual mapping is:

```text
Logical CPU Manager physical CPU set
        ↓
AllowedCPUs / cpuset.cpus

Allocation CPU entitlement
        ↓
CPUWeight / cpu.weight

Optional hard ceiling
        ↓
CPUQuota / cpu.max
```

However, this mapping is intentionally not an architectural requirement.

Implementation work must determine which combination produces the desired semantics.

---

## CPU Weight

A likely implementation strategy is to represent logical CPU entitlement through proportional CPU weight.

For example:

```text
Allocation A:
4 logical CPUs

Allocation B:
8 logical CPUs
```

could produce weights maintaining:

```text
A : B
=
1 : 2
```

The absolute weight values are less important than maintaining the intended proportional relationship.

The implementation must determine:

- appropriate weight normalization;
- allowed systemd/cgroup weight ranges;
- behavior with many Compute Units;
- rounding behavior;
- interactions with nested cgroups.

---

## CPU Quota

A hard CPU quota may conflict with unrestricted bursting because quota exhaustion can prevent a Compute Unit from consuming otherwise idle physical capacity.

Therefore CPU quota should not automatically be used merely because an Allocation requests a particular number of logical CPUs.

Quota may still be appropriate if Kloigos later introduces explicit burst ceilings or other CPU products requiring hard limits.

The implementation must validate this behavior before choosing a quota-based design.

---

## Nested cgroups

Compute Units may run workloads that create their own cgroup hierarchy.

Kubernetes/K3s is an important example.

Kloigos must therefore validate that Shared/Burstable CPU enforcement at the Compute Unit boundary remains effective when child workloads create nested cgroups.

The Compute Unit must not be able to escape:

- its Logical CPU Manager's physical CPU domain;
- its CPU scheduling entitlement at the parent boundary.

Child cgroups may divide the Compute Unit's resources internally, but they must remain constrained by the parent Compute Unit.

---

## Accounting

CPU capacity accounting is allocation-based.

For example:

```text
Logical CPU Manager capacity:
32

Allocation A:
8

Allocation B:
4

Allocation C:
8

Allocated:
20

Available:
12
```

This accounting is independent of instantaneous CPU utilization.

An idle Allocation continues to consume its logical CPU entitlement for admission-control purposes until the Allocation is released or resized.

Bursting therefore does not create additional schedulable logical capacity.

---

## Release

When an Allocation is released:

```text
Allocation CPU entitlement
        ↓
returned to
        ↓
Logical CPU Manager
```

For Shared CPU there is normally no exclusive physical CPU set to release.

Instead, logical capacity becomes available for future Allocations.

---

## Observability

Kloigos should eventually expose enough information to distinguish:

- logical CPU entitlement;
- physical CPU utilization;
- contention;
- throttling, if applicable;
- CPU Policy;
- Logical CPU Manager capacity.

This is important because a Shared Compute Unit may legitimately observe different CPU performance depending on contention.

Detailed metrics and user-facing observability are outside the initial implementation scope.

---

## Validation

Shared/Burstable CPU behavior must be validated experimentally.

At minimum, validation should cover:

### Isolation

Verify that a Compute Unit cannot execute outside the physical CPU set owned by its Logical CPU Manager.

### Proportional Contention

Create Compute Units with different logical CPU entitlements and apply sustained CPU load.

For example:

```text
CU A:
4 CPUs

CU B:
8 CPUs
```

Verify that CPU service under sustained contention approximately reflects:

```text
1 : 2
```

### Bursting

Run one active Compute Unit while other Allocations are idle.

Verify that the active Compute Unit can consume otherwise unused CPU capacity when the selected implementation is intended to be burstable.

### Contention Recovery

Activate previously idle Compute Units and verify that CPU service converges toward configured proportional entitlement.

### Overcommit

Verify admission control for:

```text
1:1
2:1
4:1
```

or other configured policies.

### Capacity Exhaustion

Verify that new Allocations are rejected when logical capacity is exhausted even if current physical CPU utilization is low.

### Nested cgroups

Run nested cgroup workloads, including K3s where practical, and verify that parent CPU constraints remain effective.

---

## Open Implementation Questions

The following questions intentionally remain open until implementation and validation:

1. Should Shared CPU use `CPUWeight`, `cpu.weight`, or another proportional mechanism?

2. Is `AllowedCPUs` sufficient for defining the physical CPU domain, or should Kloigos directly manage `cpuset.cpus`?

3. Should Shared CPU use any form of `CPUQuota` / `cpu.max`?

4. Should the initial implementation allow unrestricted bursting within the Logical CPU Manager?

5. Is an explicit burst ceiling required?

6. How should logical CPU quantities map into CPU weights?

7. How should weights be normalized across differently sized Allocations?

8. How does the selected implementation behave with SMT?

9. How does it behave across NUMA nodes?

10. How does nested cgroup delegation affect CPU entitlement?

These questions should be answered through implementation experiments rather than assumptions in the architectural model.

---

## Non-Goals

This design does not define:

- Dedicated CPU implementation;
- Host Family classification;
- Instance Class definitions;
- Logical CPU Manager persistence;
- general allocator architecture;
- NUMA-aware placement;
- SMT-aware placement;
- CPU credit systems;
- AWS-style accumulated burst credits;
- CPU utilization-based billing;
- automatic CPU Policy selection.

In particular, **Burstable CPU does not imply a CPU credit system**.

Kloigos initially defines bursting simply as the ability to consume otherwise idle physical CPU capacity within the shared CPU domain.

---

## Architectural Invariants

> **Shared CPU capacity is backed by physical CPUs owned by a Logical CPU Manager.**

> **Shared Allocations consume logical CPU capacity, not exclusive physical CPUs.**

> **The CPU Policy determines the logical capacity exposed by a Shared Logical CPU Manager.**

> **Overcommit affects admission control; it does not create physical CPU capacity.**

> **Logical CPU entitlement represents proportional CPU service during contention.**

> **Shared CPU should be work-conserving: idle physical CPU capacity may be consumed by active Compute Units.**

> **Bursting does not increase schedulable logical capacity.**

> **An idle Allocation continues to consume its logical CPU entitlement until released or resized.**

> **A Shared Compute Unit must remain within the physical CPU domain of its Logical CPU Manager.**

> **Shared 1:1 CPU is distinct from Dedicated CPU.**

> **Users normally consume Shared CPU through Instance Classes rather than selecting overcommit ratios directly.**

> **The exact Linux/systemd/cgroup implementation is not part of the architectural contract and must be determined through implementation and validation.**
