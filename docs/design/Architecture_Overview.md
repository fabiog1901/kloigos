# Kloigos Architecture Overview

## Purpose

Kloigos turns a heterogeneous bare-metal Linux fleet into a programmable internal compute cloud while allowing administrators —not application users— to own the complexity of the underlying hardware.

It provides users with dynamically allocated, isolated Linux execution environments built directly from physical server resources using standard Linux primitives.

Kloigos does not require a hypervisor or container runtime to provide these environments. Instead, it manages physical host capacity and uses Linux mechanisms such as cgroups, systemd, CPU sets, filesystem permissions, native networking, nftables, and AppArmor to construct and enforce workload boundaries.

The architecture is built around a fundamental separation:

> **Physical hosts provide capacity. Compute Units provide execution boundaries. Allocations provide durable workload identity.**

This allows the physical infrastructure to change independently from the interface presented to application users.

Administrators manage the physical fleet, hardware characteristics, capacity pools, networking, security policy, and infrastructure classes. Users request the compute resources they need without needing to understand which physical server, processor generation, storage device, network configuration, or other hardware details satisfy that request.

This document describes the high-level architectural model of Kloigos.

Detailed subsystem behavior, design tradeoffs, lifecycle semantics, and implementation-specific decisions are documented separately in the individual design documents under `docs/design/`.

## Architectural Model

At a high level:

```text
                         Kloigos Control Plane
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
           Infrastructure                    User Requests
           Administration                          │
                 │                                 │
                 ▼                                 ▼
        Heterogeneous Fleet                 Allocation Request
                 │                                 │
        ┌────────┼────────┐                        │
        │        │        │                        │
      Host A   Host B   Host C                     │
        │        │        │                        │
        └────────┴────────┘                        │
                 │                                 │
                 │        Scheduling & Policy      │
                 └──────────────┬──────────────────┘
                                │
                                ▼
                         Resource Reservation
                                │
                                ▼
                           Compute Unit
                                │
                                ▼
                            Allocation
                                │
                                ▼
                          User Workload
```

The control plane sits between two different concerns.
On one side, administrators manage heterogeneous physical infrastructure.
On the other, users request logical compute resources.
Kloigos is responsible for translating between the two.
A user should not need to know which physical server satisfies an Allocation request. Conversely, administrators should not need to manually partition every physical server into predefined workload slots.
This separation is one of the central architectural goals of Kloigos.

## Physical Hosts

Physical hosts are the source of allocatable infrastructure capacity.

A host may provide:

- dedicated CPU capacity
- shared CPU capacity
- memory
- storage
- network connectivity
- IP address capacity
- GPUs or other specialized resources

Hosts may belong to different Host Families representing different physical hardware characteristics.

Kloigos reasons about available host resources rather than treating servers as inventories of permanently predefined execution slots.

## Instance Classes

Instance Classes provide a user-facing abstraction over physical infrastructure.

They allow users to request infrastructure characteristics without selecting specific servers or hardware models.

An Instance Class may constrain placement according to characteristics such as:

- CPU architecture or performance profile
- memory characteristics
- storage capabilities
- GPU availability
- tenancy requirements

Administrators determine which Host Families satisfy each Instance Class.

Instance Classes describe eligible infrastructure and policy. They do not require administrators to pre-create Compute Units of every possible size.

## Allocations

An Allocation represents the durable identity of a workload in Kloigos.

It may own or reference resources such as:

- workload identity
- Unix identity
- network identity
- storage
- metadata
- configuration
- metering history
- current Compute Unit placement

An Allocation is intentionally distinct from the Compute Unit in which it currently executes.

This distinction allows Kloigos to change placement or reconstruct execution capacity without changing the logical identity of the workload.

## Compute Units

A Compute Unit is the concrete Linux execution boundary in which an Allocation runs.

Compute Units are not virtual machines and are not system containers.

They are constructed using standard Linux facilities such as:

- systemd
- cgroups
- CPU sets and scheduler controls
- Unix users and filesystem permissions
- Linux networking
- nftables
- AppArmor
- storage and filesystem controls

A Compute Unit defines the resources and isolation boundaries available to the workload.

Compute Units are dynamically materialized from available physical-host capacity when required rather than existing only as a fixed inventory of predefined shapes.

The detailed lifecycle and resource reservation model is defined in the **Dynamic Compute Unit Provisioning** design.

## Scheduling and Placement

When an Allocation is requested, Kloigos determines where the workload can run.

Conceptually:

```text
Allocation Request
        ↓
Instance Class and Policy
        ↓
Eligible Host Families
        ↓
Candidate Physical Hosts
        ↓
Resource and Placement Constraints
        ↓
Resource Reservation
        ↓
Compute Unit Materialization
        ↓
Allocation Activation
```

Placement may depend on multiple dimensions simultaneously, including CPU availability, memory, storage, NUMA topology, IP availability, tenancy policy, and specialized hardware.

Exclusive resources must be reserved safely so that concurrent provisioning operations cannot allocate the same resource.

Detailed scheduling behavior belongs in the **Scheduling and Placement Model** design.

## Resource Isolation

Kloigos provides resource isolation using the Linux kernel rather than virtualization.

CPU resources may be provided using Dedicated or Shared CPU models.

Memory, process counts, storage, networking, and other resources are similarly constrained using appropriate Linux facilities.

Dedicated resources must preserve exclusivity where promised. Shared resources are explicitly identified as shared rather than silently weakening dedicated-resource guarantees.

The detailed CPU model is defined in the **CPU Resource Model** design.

## Networking

Each Compute Unit receives a real IP address from an administrator-configured IP pool.

The address is configured using the physical host's native Linux networking rather than an overlay network or virtualized network stack.

Kloigos uses nftables and related Linux networking mechanisms to associate and enforce network access for the intended Compute Unit.

IP addresses are therefore first-class allocatable resources and participate in provisioning, scheduling, exhaustion handling, and cleanup.

Detailed behavior belongs in the **Networking and IP Model** design.

## Storage and Persistence

Kloigos distinguishes execution capacity from durable workload resources.

A Compute Unit may be destroyed and recreated while resources belonging to the Allocation, such as persistent storage, survive according to their lifecycle policy.

This distinction is important for resizing, recovery, migration, and future placement changes.

Detailed storage behavior belongs in the **Storage and Persistence Model** design.

## Security Model

Kloigos uses multiple standard Linux security mechanisms together rather than introducing a new isolation technology.

These include:

- Unix identities and permissions
- cgroups
- filesystem ownership and access controls
- nftables
- AppArmor
- systemd controls
- network isolation
- auditing and logging

Compute Units share the host Linux kernel. Kloigos therefore does not claim the same security boundary as hardware virtualization.

Dedicated Server Tenancy can prevent organizations from sharing the same physical host when stronger organizational isolation is required.

The threat model and security guarantees are defined in the **Security and Isolation Model** and **Tenancy Model** designs.

## Metering

Kloigos meters resources according to what is allocated rather than according to instantaneous utilization.

An Allocation holding resources incurs usage for those resources for the duration of the allocation, regardless of whether the workload continuously consumes them.

Pricing is administrator-defined and may vary by Instance Class, resource dimensions, and tenancy characteristics.

Metering remains associated with the durable Allocation even when its Compute Unit or resource configuration changes.

Detailed semantics belong in the **Metering and Pricing Model** design.

## Nested Orchestration

Because a Compute Unit provides a normal Linux execution environment, higher-level systems can run inside it.

For example, K3s can use several Compute Units as Kubernetes control-plane and worker nodes.

Nested systems may subdivide resources delegated to them, but they must remain inside the resource and security boundaries established by Kloigos.

This allows Kloigos to support container-orchestrated workloads alongside applications running directly on Linux without making Kubernetes or containers part of the Kloigos execution model.

Detailed behavior belongs in the **Nested Orchestration / Kubernetes Model** design.

## Validation

Kloigos architectural guarantees must be validated against real Linux hosts.

Validation therefore tests not only control-plane state but actual enforcement of CPU, memory, storage, networking, security, tenancy, and other boundaries.

The validation system also tests failure conditions, resource contention, provisioning cleanup, and attempts to exceed configured limits.

Detailed testing principles and execution architecture belong in the **Validation Architecture** design.

## Core Architectural Invariants

The architecture is guided by a small set of system-wide invariants:

1. **Physical hosts own allocatable infrastructure capacity.**
2. **Compute Units are concrete Linux execution boundaries created from that capacity.**
3. **Allocations are durable workload identities distinct from Compute Units.**
4. **Kloigos uses native Linux mechanisms rather than requiring virtualization or containers.**
5. **Dedicated resources must not be silently shared.**
6. **Exclusive resources must be reserved safely and released when no longer required.**
7. **Failed provisioning must not leak resources or leave partially active environments.**
8. **Durable Allocation resources must not be destroyed merely because a Compute Unit is replaced.**
9. **Networking uses administrator-provided real IP capacity rather than an overlay address space.**
10. **The control plane defines policy and placement; Linux on the physical host enforces the resulting resource boundaries.**

These invariants should remain stable even as individual implementations evolve.

## Further Design Documentation

This document intentionally describes Kloigos only at the architectural level.

Detailed decisions, tradeoffs, lifecycle behavior, failure semantics, and subsystem-specific invariants should be maintained in the corresponding design documents under:

```text
docs/design/
```

The Architecture Overview should remain concise. When a subsystem requires substantial explanation, that material belongs in its individual design document rather than expanding this overview.