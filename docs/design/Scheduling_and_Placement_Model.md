# Scheduling and Placement Model

## Purpose

Kloigos schedules Allocation requests onto physical hosts based on infrastructure compatibility, current capacity, resource topology, tenancy, networking, storage, and other placement constraints.

The scheduling model is built around a fundamental principle:

> **The scheduler does not search for a pre-existing Compute Unit. It finds a physical host from whose available capacity Kloigos can construct the required Compute Unit.**

This is a consequence of the Dynamic Compute Unit Provisioning architecture.

Physical hosts own allocatable capacity. Compute Units are materialized from that capacity when an Allocation requires execution resources.

The scheduler therefore answers:

> **Can this Allocation be realized on this host right now?**

This document defines host eligibility, capacity evaluation, placement constraints, resource reservation, and the boundary between scheduling and provisioning.

---

## Scheduling Model

At a high level:

```text
Allocation Request
        │
        ▼
Resolve Instance Class
and Allocation Constraints
        │
        ▼
Determine Eligible Host Families
        │
        ▼
Find Candidate Hosts
        │
        ▼
Apply Placement Constraints
        │
        ├── Tenancy
        ├── CPU Model
        ├── CPU Topology / NUMA
        ├── Memory
        ├── Storage / Locality
        ├── Network / IP
        └── Specialized Resources
        │
        ▼
Evaluate Available Capacity
        │
        ▼
Select Host
        │
        ▼
Atomically Reserve Resources
        │
        ▼
Dynamic CU Provisioning
```

Scheduling determines **where** the Allocation can run and which host resources should be reserved.

Provisioning then creates the actual Compute Unit.

---

## From CU Scheduling to Capacity Scheduling

An earlier Kloigos model relied on administrator-created Compute Units with predefined shapes.

Scheduling therefore resembled:

```text
Request:
4 CPU
16 GB Memory

       │
       ▼

Find unused CU
with matching shape
```

This creates stranded capacity.

For example:

```text
Host

CU-1: 4 CPU   FREE
CU-2: 4 CPU   FREE
```

An 8-CPU request cannot be satisfied even though eight CPUs are physically available.

The target architecture instead treats the host as the capacity owner:

```text
Host

8 suitable CPUs available
        │
        ▼
Request: 8 CPUs
        │
        ▼
Reserve CPUs
        │
        ▼
Create 8-CPU CU
```

The scheduling unit is therefore **host capacity**, not an inventory of predefined execution slots.

---

## Allocation Requests

An Allocation request describes the resources and infrastructure characteristics required by the workload.

Depending on the request and Instance Class, constraints may include:

- Instance Class
- CPU count
- Dedicated or Shared CPU
- memory
- storage capacity or class
- network requirements
- tenancy
- GPU or specialized resources
- topology requirements
- other administrator-defined policy

The request describes desired logical resources.

It does not need to identify a physical host or hardware model.

Kloigos resolves those requirements against the infrastructure known to the control plane.

---

## Instance Classes

Instance Classes provide the user-facing abstraction over heterogeneous infrastructure.

For example:

```text
Instance Class
compute-optimized
        │
        ├── Host Family A
        ├── Host Family B
        └── Host Family C
```

Different Host Families may contain different:

- processor generations
- CPU counts
- memory capacities
- storage devices
- network hardware
- GPU models
- server vendors

An Instance Class defines which infrastructure characteristics are appropriate for a category of workload.

It does not require every underlying physical server to be identical.

---

## Host Families

Host Families describe groups of physical servers with common infrastructure characteristics.

Conceptually:

```text
Instance Class
"compute-optimized"
       │
       ├── AMD-high-frequency-v2
       │       ├── Host-1
       │       └── Host-2
       │
       └── Intel-high-frequency-v3
               ├── Host-7
               └── Host-8
```

Administrators determine which Host Families satisfy each Instance Class.

This allows Kloigos to hide hardware complexity from application users while retaining enough infrastructure knowledge for correct scheduling.

---

## Host Eligibility

Scheduling begins by eliminating hosts that cannot satisfy hard constraints.

A host may be ineligible because of:

- incompatible Instance Class
- incompatible Host Family
- insufficient CPU capacity
- unsuitable Dedicated CPU topology
- insufficient Shared CPU logical capacity
- insufficient memory
- insufficient storage
- incompatible storage locality
- unavailable compatible IP addresses
- tenancy conflict
- unavailable GPU or specialized hardware
- administrative state
- host health or maintenance state

A host must satisfy all mandatory constraints before it can become a placement candidate.

---

## Multidimensional Capacity

Host capacity is multidimensional.

For example:

```text
Host-A

Dedicated CPU:    12 available
Shared CPU:       20 logical units available
Memory:           96 GB available
Storage:          800 GB available
IP addresses:     4 available
GPU:              0 available
```

A request for:

```text
8 Dedicated CPUs
32 GB Memory
200 GB Storage
1 IP
```

may fit.

A request for:

```text
4 Dedicated CPUs
16 GB Memory
100 GB Storage
1 GPU
```

does not.

Therefore Kloigos should not reduce capacity to a single generic number such as:

```text
Host-A has 37 capacity units
```

Whether capacity is available depends on the request being evaluated.

---

## CPU Placement

CPU placement depends on the requested CPU model.

### Dedicated CPU

A Dedicated CPU request requires suitable exclusive physical execution resources.

The scheduler must determine whether the host contains an appropriate free CPU set.

For example:

```text
Request:
8 Dedicated CPUs

        │
        ▼

Host topology
        │
        ▼

Find suitable exclusive
8-CPU placement
```

Aggregate free CPU count may be insufficient to determine eligibility because CPU topology, SMT policy, NUMA placement, and fragmentation may matter.

### Shared CPU

A Shared CPU request consumes logical capacity from the host's Shared CPU Pool.

For example:

```text
Shared physical pool:          32 CPUs
Logical capacity at 2:1:       64 Shared CPUs
Already allocated:             40
Available logical capacity:    24
```

A request for 8 Shared CPUs may therefore fit even though no eight physical CPUs are exclusively reserved for it.

Dedicated and Shared capacity must remain distinct throughout scheduling.

Detailed semantics belong in the **CPU Resource Model** design.

---

## NUMA and Topology

Physical CPU and memory topology may constrain placement.

For example:

```text
NUMA Node 0
├── CPUs 0-31
└── Local Memory

NUMA Node 1
├── CPUs 32-63
└── Local Memory
```

A request may theoretically fit based on aggregate CPU and memory while producing an undesirable or invalid placement across NUMA boundaries.

The scheduler should understand enough topology to preserve the guarantees defined by the CPU and memory resource models.

Topology-aware placement may consider:

- NUMA nodes
- sockets
- physical cores
- SMT siblings
- CPU pools
- memory locality

Initial implementations may use relatively simple topology rules.

Correctness takes precedence over sophisticated optimization.

---

## Memory Placement

Memory is tracked as host capacity.

For example:

```text
Physical Memory:     512 GB
Reserved:            320 GB
Available:           192 GB
```

A request requiring 256 GB cannot be placed on that host.

Where NUMA policy requires memory locality, aggregate free memory may not be sufficient.

For example:

```text
NUMA Node 0: 40 GB available
NUMA Node 1: 40 GB available

Total: 80 GB
```

A request requiring 64 GB on one NUMA node cannot be satisfied even though total free memory is 80 GB.

The scheduler must evaluate capacity according to the actual resource guarantees being offered.

---

## Storage Placement

Storage is a first-class placement constraint.

The scheduler must consider:

- available capacity
- storage class
- physical locality
- required performance characteristics
- existing persistent storage

For a new Allocation:

```text
Request
500 GB high-performance storage
        │
        ▼
Candidate Host
        │
        ▼
Compatible storage pool?
        │
        ▼
Enough available capacity?
```

For an existing Allocation, persistent local storage may constrain placement to the host where that storage currently resides.

Moving the Allocation elsewhere may first require an explicit storage migration mechanism.

The scheduler must not treat local persistent storage as transparently portable.

Detailed behavior belongs in the **Storage and Persistence Model** design.

---

## Network Placement

IP addresses are schedulable infrastructure resources.

A host with sufficient CPU, memory, and storage is not eligible if Kloigos cannot assign a compatible IP address to the Allocation.

For example:

```text
Host-A

CPU:       available
Memory:    available
Storage:   available
IP:        unavailable

Result: ineligible
```

IP compatibility may depend on:

- IP pool
- subnet
- network
- VLAN
- site
- host network attachment

The scheduler must evaluate network compatibility before committing placement.

Detailed behavior belongs in the **Networking and IP Model** design.

---

## Tenancy Placement

Tenancy is a hard host eligibility constraint.

Under Shared Tenancy, Allocations belonging to multiple organizations may share a host.

Under Dedicated Server Tenancy, only Allocations belonging to the owning organization may use the host.

For example:

```text
Host-7
Dedicated to Organization A

Request from Organization A
        ✓ eligible

Request from Organization B
        ✗ ineligible
```

A host with substantial unused resources remains unavailable to another organization while dedicated tenancy is active.

A request for Dedicated Server Tenancy may also require Kloigos to acquire an eligible unowned host or use a host already dedicated to the requesting organization.

Detailed semantics belong in the **Tenancy Model** design.

---

## Existing Allocation Placement

Scheduling is not limited to initial Allocation creation.

It may also occur when an existing Allocation needs a new Compute Unit because of:

- resizing
- host maintenance
- recovery
- placement changes
- infrastructure replacement
- future migration workflows

In these cases, the Allocation may already own durable resources such as:

- persistent storage
- IP identity
- security configuration

Those resources may constrain destination eligibility.

For example:

```text
Allocation A
├── IP requiring Network X
└── Storage currently local to Host-A
```

A destination host must satisfy the constraints required to preserve those resources, or the placement workflow must explicitly migrate or replace them.

---

## Candidate Selection

After hard constraints are applied, multiple hosts may remain eligible.

For example:

```text
Eligible Hosts

Host-A
Host-B
Host-C
Host-D
```

Kloigos then selects one candidate.

Initial selection policy should remain intentionally simple and deterministic.

Possible considerations include:

- preserving large contiguous CPU sets
- avoiding unnecessary NUMA fragmentation
- consolidating Shared CPU workloads
- preserving hosts suitable for large requests
- minimizing stranded capacity
- using already-dedicated hosts for their owning organization

However, sophisticated global optimization is not required for the initial architecture.

The primary scheduler goal is:

> **Produce a correct placement that satisfies all requested guarantees without violating existing reservations.**

Optimization can evolve independently.

---

## Fragmentation

Dynamic provisioning removes much of the shape fragmentation caused by pre-created Compute Units, but physical resource fragmentation still exists.

For example:

```text
Host

8 CPUs free in total
```

does not necessarily mean:

```text
Any 8-CPU Dedicated request fits
```

The free CPUs may be distributed across:

- NUMA nodes
- sockets
- fragmented cpusets
- incompatible CPU pools

Likewise, storage or other specialized resources may be fragmented.

The scheduler must therefore evaluate whether a specific request can be constructed from available resources rather than relying only on aggregate totals.

---

## Reservation

Host selection alone is not sufficient.

Once Kloigos determines that a host can satisfy a request, the required resources must be reserved before provisioning begins.

Conceptually:

```text
Select Host
     │
     ▼
Atomic Resource Reservation
     │
     ├── CPU
     ├── Memory
     ├── Storage
     ├── IP
     ├── Tenancy
     └── Specialized Resources
            │
            ▼
       Provision Compute Unit
```

Reservation prevents another concurrent scheduling operation from consuming the same capacity.

---

## Atomicity

Resource reservation is a multi-resource operation.

Consider two simultaneous requests that both observe:

```text
8 Dedicated CPUs available
1 compatible IP available
```

Both must not successfully reserve the same CPUs or IP.

Likewise, Kloigos must avoid partial reservations such as:

```text
CPU reserved
Memory reserved
IP reservation FAILED

Result:
CPU and memory permanently leaked
```

The reservation operation must either successfully secure the resources required for the placement or safely release resources acquired during the failed attempt.

The exact transaction mechanism is an implementation concern.

The atomicity guarantee is architectural.

---

## Scheduling and Provisioning Boundary

Scheduling and provisioning are separate responsibilities.

### Scheduler

The scheduler determines:

- which hosts are eligible
- whether sufficient compatible capacity exists
- which host should be selected
- which resources must be reserved

### Provisioner

The provisioner takes the reservation and materializes the Compute Unit.

For example:

```text
Scheduler
   │
   │ placement decision
   ▼
Host-7
CPUs 12-19
32 GB Memory
200 GB Storage
IP 10.20.30.41
   │
   ▼
Provisioner
   │
   ├── create cgroups
   ├── configure cpuset
   ├── configure memory
   ├── create/attach storage
   ├── configure networking
   ├── apply security policy
   └── configure workload identity
   │
   ▼
Compute Unit
```

The scheduler decides **what should be reserved and where**.

The provisioner makes that decision real.

---

## Provisioning Failure

A valid scheduling decision does not guarantee that provisioning will succeed.

For example:

```text
Placement selected
        │
        ▼
Resources reserved
        │
        ▼
Provisioning
        │
        ├── CPU configured
        ├── Memory configured
        ├── Storage configured
        └── Network FAILED
```

The Allocation must not become ACTIVE.

The failed Compute Unit must be cleaned up and reusable capacity returned safely.

Depending on failure policy, Kloigos may later attempt another placement.

A host must not immediately regain capacity in scheduler state while stale host-side configuration still consumes or controls that resource.

Detailed rollback belongs in the **Dynamic Compute Unit Provisioning** design.

---

## Host State

Not every host with free resources should necessarily accept new placements.

Administrative or operational state may make a host unavailable.

Examples include:

- maintenance
- draining
- provisioning
- degraded health
- unavailable
- dedicated tenancy transition

Conceptually:

```text
Host Capacity Available
        │
        ▼
Host Accepting Placements?
        │
       No
        │
        ▼
     Ineligible
```

Host operational state is therefore independent from raw resource availability.

The exact host state machine may evolve.

---

## Capacity Reporting

Kloigos should expose capacity in terms that preserve meaningful resource distinctions.

For example:

```text
Host-7

Dedicated CPU
  Physical:    32
  Allocated:   24
  Available:    8

Shared CPU
  Physical:    32
  Logical:     64
  Allocated:   40
  Available:   24

Memory
  Physical:   512 GB
  Allocated:  320 GB
  Available:  192 GB

Storage
  Available:  1.4 TB

IP
  Available:  12
```

However, capacity reporting must not imply that every combination of these available values can necessarily be allocated together.

Topology, locality, tenancy, and compatibility may still prevent a particular request.

The authoritative capacity question remains:

> **Can this host satisfy this specific request?**

---

## Compatibility with Pre-Created Compute Units

Existing Kloigos deployments may contain pre-created Compute Units.

Migration to dynamic scheduling does not require active Allocations to be disrupted.

A transition strategy may allow:

- active existing CUs to remain until released
- free static CU inventory to be converted back into host capacity
- new hosts to use dynamic provisioning exclusively
- static and dynamic models to coexist temporarily during migration

The target architecture remains host-capacity scheduling.

Pre-created Compute Units are a compatibility concern rather than the long-term scheduling abstraction.

---

## Validation Requirements

Scheduling must be validated against real resource state and concurrent operations.

Validation should include at minimum:

### Basic Placement

- eligible host selected
- incompatible Instance Classes rejected
- Host Family constraints honored
- sufficient CPU required
- sufficient memory required
- sufficient storage required
- compatible IP required

### CPU

- Dedicated CPU availability
- Shared CPU logical capacity
- Dedicated and Shared Pool separation
- topology constraints
- NUMA constraints
- fragmented capacity behavior

### Storage

- storage capacity
- storage class
- local persistent-storage constraints

### Networking

- compatible IP pool
- IP exhaustion
- network incompatibility

### Tenancy

- Shared Tenancy placement
- Dedicated Server Tenancy ownership
- foreign organizations rejected from dedicated hosts
- unused dedicated capacity excluded from general availability

### Concurrency

- CPUs cannot be double-reserved
- IPs cannot be double-reserved
- storage cannot be oversubscribed accidentally
- dedicated host ownership cannot be acquired concurrently by different organizations

### Failure

- failed reservation releases partial reservations
- failed provisioning eventually returns reusable capacity
- stale host state prevents premature reuse
- scheduler state remains consistent with physical enforcement

Detailed execution belongs in the **Validation Architecture** design.

---

## Architectural Invariants

The Kloigos scheduling and placement model is governed by the following invariants:

1. **Physical hosts own allocatable infrastructure capacity.**

2. **The scheduler selects host capacity from which a Compute Unit can be materialized rather than requiring a pre-existing matching Compute Unit.**

3. **Instance Classes describe user-facing infrastructure characteristics and may map to multiple Host Families.**

4. **Placement is multidimensional and must consider all mandatory resource and policy constraints.**

5. **Dedicated CPU and Shared CPU capacity must remain distinct during scheduling.**

6. **Aggregate free CPU does not imply that a particular Dedicated CPU request can be satisfied.**

7. **CPU topology and NUMA may constrain placement.**

8. **Storage capacity and locality are placement constraints.**

9. **Compatible IP availability is a placement constraint.**

10. **Tenancy is a hard host eligibility constraint.**

11. **Unused capacity on a dedicated host must not be considered available to other organizations.**

12. **Existing durable Allocation resources may constrain fu
