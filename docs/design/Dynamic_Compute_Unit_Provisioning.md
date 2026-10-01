# Dynamic Compute Unit Provisioning

## Status

Design proposal.

## Summary

Kloigos should transition from a model in which Compute Units are pre-created by administrators into a model in which **Compute Units are dynamically materialized from available physical host capacity when an Allocation is requested**.

Today, the administrator prepares a fixed inventory of Compute Units with predefined CPU, memory, and other resource assignments. Provisioning selects an existing available Compute Unit that matches the user's request.

The proposed model changes the fundamental scheduling question from:

> **Is there an existing available Compute Unit matching this request?**

to:

> **Can Kloigos construct the requested Compute Unit from the currently available resources on an eligible physical host?**

A Compute Unit remains a concrete Kloigos resource boundary, but it no longer needs to exist before it is needed.

Conceptually:

```text
Physical Host Capacity
        ↓
Allocation Request
        ↓
Scheduler
        ↓
Reserve Required Resources
        ↓
Materialize Compute Unit
        ↓
Attach Allocation
        ↓
Workload Runs
```

When the Compute Unit is no longer required, its reusable resources return to the host's available capacity.

This design enables arbitrary or administrator-controlled Compute Unit sizing, reduces stranded capacity, simplifies future Shared CPU support, and makes Kloigos behave more like a true bare-metal compute capacity platform.

---

# 1. Motivation

The existing Kloigos model requires administrators to predict which Compute Unit shapes users will need.

For example, an administrator might prepare:

```text
Host
│
├── CU-1 → 4 CPU / 16 GiB
├── CU-2 → 4 CPU / 16 GiB
├── CU-3 → 8 CPU / 32 GiB
└── CU-4 → 8 CPU / 32 GiB
```

A user requesting:

```text
8 CPU
32 GiB
```

can consume one of the existing 8-CPU Compute Units.

However, fixed Compute Unit inventory can strand otherwise usable physical capacity.

For example:

```text
Available:
  2 × 4-CPU Compute Units

Request:
  1 × 8-CPU Compute Unit

Physical CPU available: 8
Matching pre-created CU: none

Result:
  provisioning fails
```

The physical host has enough unused capacity to satisfy the request, but the pre-partitioned Compute Unit inventory prevents Kloigos from using it.

The administrator must therefore predict workload shapes in advance.

That becomes increasingly difficult as Kloigos supports:

- different Instance Classes
- Dedicated CPU
- Shared CPU
- arbitrary CPU counts
- memory sizing
- storage sizing
- GPUs and accelerators
- NUMA-aware placement
- Shared and Dedicated Tenancy
- multiple IP pools
- heterogeneous hardware

Dynamic Compute Unit provisioning removes this unnecessary constraint.

---

# 2. Core Design Principle

The physical host should expose **allocatable capacity**, not primarily a pre-created inventory of Compute Units.

A Compute Unit should be materialized when Kloigos successfully reserves the resources required by an Allocation.

The model becomes:

```text
HOST
    owns allocatable physical resources

COMPUTE UNIT
    is a concrete resource boundary dynamically
    materialized from host capacity

ALLOCATION
    is the durable workload identity attached
    to that Compute Unit
```

The existing distinction between Compute Unit and Allocation remains important.

Dynamic provisioning strengthens rather than removes that distinction.

---

# 3. Resource Model

A physical host exposes capacity across multiple resource dimensions.

Conceptually:

```yaml
host:
  cpu:
    total: 64
    dedicated_pool: "0-31"
    shared_pool: "32-63"

  memory:
    total: 512GiB
    allocatable: 448GiB

  storage:
    pool: kloigos-vg
    allocatable: 8TiB

  network:
    ip_pools:
      - production

  accelerators: []
```

The exact schema is implementation-specific and should not be frozen by this design document.

The important principle is that Kloigos tracks the difference between:

```text
Physical Capacity
Reserved Capacity
Available Capacity
```

for every schedulable resource.

---

# 4. Dynamic Provisioning Flow

A user submits an Allocation request.

For example:

```yaml
allocation:
  organization: payments-team

  instance_class: compute-optimized

  resources:
    cpu: 6
    memory: 24GiB

  cpu_policy: dedicated

  storage:
    size: 200GiB

  network:
    ip_pool: production

  security_groups:
    - backend

  ssh_keys:
    - operations
```

Kloigos resolves the request through the scheduler.

Conceptually:

```text
Allocation Request
        │
        ├── Instance Class
        ├── CPU
        ├── CPU Policy
        ├── Memory
        ├── Storage
        ├── Accelerator Requirements
        ├── Tenancy
        ├── Network / IP Requirements
        └── Additional Constraints
                 │
                 ▼
        Resolve Instance Class
                 │
                 ▼
        Eligible Host Families
                 │
                 ▼
        Candidate Physical Hosts
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
       Materialize Compute Unit
                 │
                 ▼
          Attach Allocation
                 │
                 ▼
        Configure Environment
                 │
                 ▼
              ACTIVE
```

---

# 5. Compute Unit Materialization

Once resources have been successfully reserved, Kloigos creates the concrete Compute Unit boundary.

Depending on the requested configuration, this may include:

- cgroup hierarchy
- systemd configuration
- CPU cpuset
- CPU scheduling policy
- memory limits
- PID/task limits
- NUMA placement
- storage/LVM resources
- filesystem ownership
- Unix identity integration
- network configuration
- IP assignment
- nftables policy
- Security Groups
- AppArmor policy
- SSH access configuration

The Compute Unit therefore remains a real system object.

The change is only that it is created **just in time** rather than pre-created as idle inventory.

---

# 6. Dedicated CPU Provisioning

Dedicated CPU remains based primarily on cpuset isolation.

For example:

```text
Host Dedicated Pool
CPUs 0-31

Current allocations:

CU-A → CPUs 0-3
CU-B → CPUs 4-11

Available:
CPUs 12-31
```

A request arrives:

```yaml
resources:
  cpu: 6

cpu_policy: dedicated
```

The scheduler identifies six suitable CPUs:

```text
CPUs 12-17
```

and reserves them atomically.

The resulting Compute Unit receives:

```text
cpuset = 12-17
```

Those CPUs are removed from the available Dedicated CPU pool until the Compute Unit is released.

The fundamental Dedicated CPU invariant remains:

> **A physical CPU assigned as Dedicated CPU to one active Compute Unit must not simultaneously be allocated to another Compute Unit.**

---

# 7. Shared CPU Provisioning

Dynamic Compute Unit provisioning is also the foundation for Shared CPU.

A host may divide physical CPU capacity into separate pools.

For example:

```text
64-CPU Host
│
├── Dedicated CPU Pool
│   CPUs 0-31
│
└── Shared CPU Pool
    CPUs 32-63
```

Dedicated Compute Units receive exclusive CPU assignments from the Dedicated pool.

Shared Compute Units execute within the Shared pool.

Conceptually:

```text
Shared Pool
CPUs 32-63
     │
     ├── Shared CU-A
     ├── Shared CU-B
     ├── Shared CU-C
     ├── Shared CU-D
     └── Shared CU-E
```

Linux scheduling distributes execution time among active Shared Compute Units.

Shared CPU may use cgroup v2 CPU weighting and related scheduler controls.

The exact entitlement, weighting, bursting, and optional quota semantics belong to the Shared CPU design and should not be prematurely fixed here.

Dynamic provisioning only requires the scheduler and host resource model to distinguish:

```text
Dedicated Physical CPU Capacity

versus

Shared CPU Capacity
```

---

# 8. CPU Pool Configuration

Administrators should control how host CPU resources are made available.

For example:

```yaml
cpu_pools:
  dedicated:
    cpus: "0-31"

  shared:
    cpus: "32-63"
    overcommit_ratio: 2.0
```

This could represent:

```text
Physical CPUs:          64

Dedicated physical:     32
Shared physical:        32

Shared logical capacity:
  32 × 2.0 = 64 shared CPU units
```

The precise configuration model requires implementation design.

Kloigos should not assume that every host must expose both pools.

Valid hosts could include:

```text
100% Dedicated CPU

100% Shared CPU

Mixed Dedicated + Shared CPU
```

---

# 9. NUMA Awareness

CPU pool construction and dynamic Compute Unit placement should be NUMA-aware.

For example, on suitable hardware:

```text
NUMA Node 0
CPUs 0-31
Memory local to Node 0
        ↓
Dedicated Pool


NUMA Node 1
CPUs 32-63
Memory local to Node 1
        ↓
Shared Pool
```

This can provide stronger locality and reduce interference.

However, Kloigos must not require a one-NUMA-node-per-pool architecture.

Physical hardware varies significantly.

NUMA topology should instead be another scheduler input.

The scheduler should avoid unnecessarily poor CPU/memory placement and should preserve explicit NUMA requirements where requested.

---

# 10. Memory

Memory should also be allocated dynamically.

The scheduler tracks available host memory and reserves the requested amount when creating the Compute Unit.

For example:

```text
Host Allocatable Memory:
448 GiB

Currently Reserved:
300 GiB

Available:
148 GiB
```

A request for:

```text
24 GiB
```

can be satisfied if all other constraints are also valid.

After reservation:

```text
Available:
124 GiB
```

Memory allocation must remain compatible with NUMA placement where applicable.

---

# 11. Storage

Storage should participate in the same dynamic resource decision.

For example:

```text
Host LVM Pool
8 TiB available
```

A request:

```yaml
storage:
  size: 500GiB
```

causes the scheduler/provisioning system to reserve and materialize the required storage.

Storage lifecycle may differ from CPU and memory because persistent Allocation storage may need to survive Compute Unit replacement or movement.

Therefore:

> **Dynamic Compute Unit teardown must not imply automatic destruction of durable Allocation storage.**

Compute Unit lifecycle and storage lifecycle must remain explicitly separated.

---

# 12. Networking and IP Capacity

IP addresses remain first-class schedulable resources.

A candidate host is not valid unless an appropriate IP address can be allocated from a compatible administrator-provided IP pool.

For example:

```text
CPU available:       YES
Memory available:    YES
Storage available:   YES
Tenancy compatible:  YES
IP available:        NO

Result:
Host cannot satisfy request.
```

Resource allocation must account for the complete request rather than selecting a host based only on CPU and memory.

---

# 13. Instance Classes

Dynamic provisioning changes Instance Classes from collections of pre-created CU shapes into **constraints over eligible infrastructure**.

For example:

```yaml
instance_class:
  name: compute-optimized

  host_families:
    - amd-epyc-high-frequency
    - intel-xeon-high-frequency

  cpu_policy:
    - dedicated
```

A user could then request:

```yaml
instance_class: compute-optimized

resources:
  cpu: 6
  memory: 24GiB
```

The Instance Class determines what kind of infrastructure may satisfy the request.

The requested resource size determines how much capacity Kloigos materializes.

---

# 14. Administrator-Controlled Sizes

Dynamic provisioning does not require Kloigos to expose unrestricted arbitrary sizing.

The mechanism should support administrator policy.

An administrator may permit continuous ranges:

```yaml
cpu:
  min: 1
  max: 64
  increment: 1

memory:
  min: 2GiB
  max: 256GiB
  increment: 1GiB
```

Another administrator may expose standardized sizes:

```yaml
allowed_sizes:
  - cpu: 2
    memory: 8GiB

  - cpu: 4
    memory: 16GiB

  - cpu: 8
    memory: 32GiB

  - cpu: 16
    memory: 64GiB
```

Both use the same dynamic provisioning architecture.

The difference is product/administrator policy.

Principle:

> **Dynamic infrastructure allocation and permitted user-facing sizes are separate concerns.**

---

# 15. Atomic Resource Reservation

Dynamic provisioning introduces an important concurrency requirement.

Resource reservation must be atomic.

Kloigos must never partially allocate a request in a way that allows another concurrent request to consume the same resource.

For example:

```text
Host has:
4 dedicated CPUs available

Request A:
4 dedicated CPUs

Request B:
4 dedicated CPUs

Both arrive concurrently.
```

Exactly one request may reserve those CPUs.

The system must never produce:

```text
CU-A → CPUs 20-23

CU-B → CPUs 20-23
```

The same principle applies to:

- memory
- storage
- IP addresses
- GPUs
- tenancy ownership
- other exclusive resources

Where a multi-resource reservation fails, Kloigos must either roll back the reservation or use a transaction/reservation model that prevents partial allocation from becoming visible.

---

# 16. Provisioning State Model

Dynamic creation should use explicit lifecycle states.

Conceptually:

```text
REQUESTED
    ↓
SCHEDULING
    ↓
RESERVED
    ↓
PROVISIONING
    ↓
ACTIVE
```

Failures may transition through states such as:

```text
PROVISIONING
    ↓
FAILED
    ↓
CLEANUP
```

The exact state model should be determined during implementation.

The important requirement is that resource ownership remains deterministic during failures.

A failed provisioning operation must not silently leak:

- CPUs
- memory reservations
- IP addresses
- storage
- tenancy locks
- other capacity

---

# 17. Compute Unit Teardown

When a Compute Unit is no longer required:

```text
Allocation releases CU
        ↓
Stop/clean workload environment
        ↓
Remove Compute Unit-specific state
        ↓
Release reusable resources
        ↓
Host capacity becomes available
```

Resources may include:

- Dedicated CPUs
- Shared CPU entitlement
- memory
- temporary storage
- IP addresses
- cgroup/systemd state
- network policy
- temporary filesystem state

However, Allocation-owned durable resources must follow their own lifecycle.

Examples include potentially:

- durable storage
- Allocation identity
- historical metering
- SSH key associations
- Security Group associations

The distinction remains:

> **Destroying a Compute Unit is not necessarily the same as destroying the Allocation.**

---

# 18. Migration

Dynamic provisioning naturally supports future Allocation movement.

Conceptually:

```text
Allocation A
     │
     ├── Compute Unit on Host 17
     │
     └── migrate
            ↓
       Scheduler finds Host 42
            ↓
       Reserve destination resources
            ↓
       Materialize new Compute Unit
            ↓
       Move/reconstruct Allocation environment
            ↓
       Release old Compute Unit
```

The Allocation remains the durable identity.

The Compute Unit is the replaceable execution boundary.

This architecture makes that distinction explicit.

---

# 19. Metering

Metering remains based on the resources allocated to the Allocation.

Dynamic Compute Unit creation does not change the fundamental Kloigos metering rule:

> **Bill allocated capacity, not observed utilization.**

For Dedicated CPU, allocated capacity corresponds to reserved physical CPU resources.

For Shared CPU, the billable unit must be defined by the Shared CPU product model.

Changes to resource size or CPU policy create new metering segments.

---

# 20. Capacity Reporting

Kloigos should expose available capacity based on resources that can actually be materialized.

For example:

```text
Host 17

Dedicated CPU:
  physical:   32
  allocated:  20
  available:  12

Shared CPU:
  physical:          32
  overcommit ratio:  2.0
  logical capacity:  64
  allocated:         44
  available:         20

Memory:
  allocatable: 448 GiB
  allocated:   300 GiB
  available:   148 GiB

Storage:
  available:   4.2 TiB

IP Pool:
  available:   37
```

Instance Class capacity can be aggregated across eligible hosts.

Because multiple resource dimensions interact, aggregate capacity may sometimes need to be expressed as approximate or request-dependent rather than as a single scalar.

---

# 21. Fragmentation

Dynamic allocation reduces shape-based stranded capacity but introduces physical-resource fragmentation.

For example:

```text
Available Dedicated CPUs:

0-1
4-5
9
12-13
```

Seven CPUs may be free in total, but topology or contiguous-placement requirements may prevent certain requests.

The scheduler should therefore consider:

- cpuset topology
- NUMA locality
- sibling/thread relationships
- fragmentation
- future placement efficiency

Initial implementation does not need sophisticated bin-packing optimization.

Correctness should come first.

However, the architecture must not assume that:

```text
total free CPU count
```

is always sufficient to determine placement eligibility.

---

# 22. Scheduler Evolution

The scheduler changes from an inventory matcher into a capacity allocator.

Old conceptual behavior:

```text
Request
    ↓
Find pre-created available CU
    ↓
Allocate CU
```

New behavior:

```text
Request
    ↓
Resolve requirements
    ↓
Find eligible hosts
    ↓
Evaluate multidimensional capacity
    ↓
Select placement
    ↓
Reserve resources
    ↓
Materialize CU
    ↓
Attach Allocation
```

This is a significant scheduler evolution and should be treated as such.

---

# 23. Validation Requirements

The Kloigos Validation Harness must validate dynamic Compute Unit provisioning on real hosts.

Tests should include:

```text
✓ requested CU is created dynamically

✓ requested CPU count is correctly assigned

✓ requested memory limit is correctly assigned

✓ Dedicated CPU cpuset contains the expected number of CPUs

✓ Dedicated CPUs are not assigned to another active CU

✓ Shared CUs remain inside the Shared CPU pool

✓ host capacity decreases after reservation

✓ host capacity returns after teardown

✓ unsupported resource size is rejected

✓ insufficient CPU fails cleanly

✓ insufficient memory fails cleanly

✓ insufficient storage fails cleanly

✓ IP exhaustion fails cleanly

✓ tenancy conflicts reject placement

✓ Host Family / Instance Class constraints are honored

✓ NUMA requirements are honored

✓ concurrent reservations cannot allocate the same exclusive resource

✓ failed provisioning releases reservations

✓ CU teardown removes temporary system state

✓ durable Allocation state survives CU replacement where required

✓ metering begins and ends at the correct lifecycle points
```

---

# 24. Contention Validation

Dynamic provisioning must also participate in the normal Kloigos contention tests.

Example:

```text
CU-A → Dedicated CPU workload
CU-B → Dedicated CPU workload
CU-C → Shared CPU workload
CU-D → Shared CPU workload
CU-E → Memory pressure
CU-F → Storage pressure
```

Validation must prove that dynamically materialized boundaries remain correct under simultaneous load.

---

# 25. Failure Handling

Provisioning failures are expected infrastructure events and must be handled deterministically.

Examples include:

- host becomes unavailable during provisioning
- Ansible operation fails
- LVM creation fails
- IP configuration fails
- nftables configuration fails
- SSH configuration fails
- AppArmor configuration fails
- resource reservation becomes invalid
- host health changes during placement

The system must:

1. identify the failed provisioning attempt
2. preserve useful diagnostics
3. clean up partial Compute Unit state
4. release resources that were reserved but not successfully activated
5. avoid exposing a partially configured Allocation as ACTIVE

---

# 26. Relationship to Existing Features

Dynamic Compute Unit provisioning composes with existing Kloigos capabilities.

### Dedicated Tenancy

The scheduler must ensure the candidate host is tenancy-compatible before materializing the CU.

### Instance Classes

Instance Classes determine eligible Host Families and infrastructure characteristics.

### Host Families

Host Families describe the physical hardware on which dynamic CUs may be constructed.

### IP Pools

An address must be reservable as part of provisioning.

### Security Groups

Security policy is applied when the Allocation network environment is materialized.

### SSH Keys

Selected public keys are installed into the Allocation environment.

### Metering and Pricing

Metering begins according to the Allocation lifecycle and records the dynamically allocated resource shape.

### K3s

A dynamically provisioned CU can be configured for nested cgroup delegation where required.

---

# 27. Compatibility / Migration from Pre-Created CUs

Existing installations may already contain pre-created Compute Units.

The implementation plan must determine how those installations transition.

Possible approaches include:

- support both static and dynamic Compute Units temporarily
- migrate existing free CU inventory back into host capacity
- retain existing active CUs until their Allocations terminate
- introduce dynamic provisioning only for newly configured hosts

This design document does not prescribe the migration mechanism.

The implementation must avoid disrupting active Allocations.

---

# 28. Non-Goals

This design does not attempt to define:

- sophisticated global bin-packing algorithms
- predictive workload scheduling
- automatic host power management
- automatic hardware procurement
- Shared CPU weight mathematics
- Shared CPU SLA semantics
- live process migration
- automatic cross-datacenter migration
- arbitrary memory overcommit
- storage overcommit policy

Those may be separate designs.

The purpose of this feature is to establish **dynamic Compute Unit materialization from real available host capacity**.

---

# 29. Implementation Principle

The key architectural transition is:

```text
OLD

Administrator
    ↓
Pre-creates CU inventory
    ↓
Scheduler selects matching CU
    ↓
Allocation


NEW

Administrator
    ↓
Defines host capacity and policy
    ↓
User requests resources
    ↓
Scheduler reserves capacity
    ↓
Kloigos materializes CU
    ↓
Allocation
```

This should become the normal Kloigos provisioning model.

---

# 30. Architectural Invariants

> **Physical Hosts own allocatable capacity.**

> **Compute Units are concrete Linux resource boundaries materialized from that capacity.**

> **Allocations remain durable workload identities distinct from Compute Units.**

> **A Compute Unit does not need to exist before an Allocation requests it.**

> **Exclusive resources must be reserved atomically.**

> **Dedicated CPUs must never be simultaneously assigned to multiple active Compute Units.**

> **Shared CPU and Dedicated CPU capacity must remain explicitly distinguishable.**

> **A failed provisioning operation must not leak reserved resources.**

> **Compute Unit teardown returns reusable capacity to the host.**

> **Compute Unit teardown must not accidentally destroy durable Allocation resources.**

> **Instance Classes describe eligible infrastructure characteristics, not a mandatory inventory of pre-created CU shapes.**

> **Administrator policy may restrict allowed sizes without requiring pre-created Compute Units.**

---

# 31. Product Significance

Dynamic Compute Unit provisioning changes Kloigos from a system that allocates pre-partitioned Linux execution slots into a system that **constructs execution capacity from a bare-metal resource pool on demand**.

Instead of asking:

```text
"Which existing Compute Unit can I give this user?"
```

Kloigos asks:

```text
"Which physical host can satisfy this Allocation,
and what Compute Unit should I construct there?"
```

That is a more flexible and cloud-like infrastructure model.

It:

- reduces stranded capacity
- removes the need to predict CU shapes
- enables unusual CPU sizes
- enables Shared CPU
- improves heterogeneous hardware utilization
- strengthens the Compute Unit / Allocation distinction
- allows administrator-controlled resource catalogs without hard-coding physical partitions
- creates a stronger foundation for future scheduling and capacity management

The result remains Linux-native:

```text
Physical Linux Capacity
        ↓
Kloigos Scheduler
        ↓
Dynamic Compute Unit
        ↓
Standard Linux Resource Controls
        ↓
Allocation
```

No hypervisor or mandatory container layer is required.
