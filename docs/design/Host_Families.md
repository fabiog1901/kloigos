# Host Families

## Overview

A **Host Family** is an administrator-defined classification of physical Hosts with similar hardware characteristics.

Host Families provide a stable abstraction between discovered hardware and higher-level Kloigos resource models such as Instance Classes.

```text
Physical Host
      |
      v
Discovered Hardware Attributes
      |
      v
Host Family
      |
      v
Instance Class eligibility
```

Kloigos discovers what hardware a Host has.

The administrator decides what that hardware means within their environment.

---

## Host Attributes

Kloigos should discover factual hardware characteristics such as:

- CPU architecture;
- CPU vendor and model;
- sockets, cores, and threads;
- NUMA topology;
- memory capacity;
- GPU/accelerator inventory;
- relevant storage characteristics.

These attributes describe the physical machine.

They do not themselves define a Host Family.

---

## Administrator Classification

Administrators define Host Families appropriate to their infrastructure.

Examples:

```text
amd-epyc-gen4
intel-xeon-gen5
intel-xeon-legacy
gpu-h100
storage-dense-gen2
```

A Host is assigned to a Host Family either explicitly or through deterministic administrator-defined matching rules.

Kloigos should not maintain a universal taxonomy mapping hardware models into predefined commercial categories.

---

## Relationship to Instance Classes

Host Families are infrastructure-facing.

Instance Classes are user-facing.

An Instance Class may allow one or more Host Families:

```text
Instance Class: general-purpose

Eligible Host Families:
- amd-epyc-gen4
- intel-xeon-gen5
```

This creates a many-to-many relationship:

```text
Host Families
      |
      | many-to-many
      v
Instance Classes
```

A Host Family may support multiple Instance Classes, and an Instance Class may run on multiple Host Families.

---

## Relationship to CPU Policy

Host Family and CPU Policy describe different dimensions.

```text
Host Family
    = what hardware is this?

CPU Policy
    = how is CPU capacity delivered?
```

A Host Family does not define whether CPU resources are Dedicated, Shared, or overcommitted.

That behavior belongs to CPU Policies.

---

## Relationship to Logical CPU Managers

A Host belongs to a Host Family.

The Host may contain one or more Logical CPU Managers implementing different CPU Policies.

Example:

```text
Host
Family: amd-epyc-gen4

├── Logical CPU Manager
│   ├── CPUs 0-31
│   └── Policy: dedicated
│
└── Logical CPU Manager
    ├── CPUs 32-63
    └── Policy: shared-standard
```

The Host Family classifies the Host.

Logical CPU Managers control how portions of that Host's CPU resources are allocated.

---

## Tags

Host Families should remain distinct from general Host metadata or tags.

For example:

```text
Host Family:
amd-epyc-gen4

Tags:
datacenter=nyc1
rack=r12
environment=production
```

Host Family represents a deliberate hardware classification used by placement.

Tags represent additional metadata that may independently participate in administration or placement.

---

## Design Invariants

> Host attributes describe discovered physical hardware.

> Host Families are administrator-defined classifications of that hardware.

> Kloigos does not impose a universal hardware-family taxonomy.

> A Host belongs to a Host Family used for placement eligibility.

> Host Families describe hardware characteristics, not CPU sharing behavior.

> CPU delivery behavior belongs to CPU Policies.

> Instance Classes may reference multiple eligible Host Families.

> Host Families are distinct from arbitrary Host tags.
