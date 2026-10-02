# CPU Resource Model

## Purpose

Kloigos exposes physical CPU capacity through two explicit resource models:

- **Dedicated CPU** — physical CPU execution resources are reserved exclusively for a Compute Unit.
- **Shared CPU** — multiple Compute Units execute within a controlled shared CPU pool and are scheduled by Linux.

The core principle is:

> **Dedicated CPU provides exclusivity. Shared CPU provides controlled statistical multiplexing. Kloigos never silently converts one into the other.**

This document defines the CPU capacity model, host CPU pools, allocation semantics, topology considerations, and the boundaries between CPU policy and Linux enforcement.

Detailed provisioning, placement, metering, and validation behavior belongs in their respective design documents.

---

## CPU Capacity Model

A physical host contributes CPU capacity to Kloigos.

That capacity may be divided into two pools:

```text
Physical Host CPUs
        │
        ├────────────────────────┐
        │                        │
        ▼                        ▼
Dedicated CPU Pool         Shared CPU Pool
        │                        │
        ▼                        ▼
Exclusive CPU sets        Shared scheduling
        │                        │
        ▼                        ▼
Dedicated CUs             Shared CUs
```

Administrators determine how much of a host's CPU capacity belongs to each pool.

A host may therefore be:

- entirely Dedicated CPU
- entirely Shared CPU
- a mixture of Dedicated and Shared CPU

The two pools must remain explicitly distinguishable in capacity accounting and scheduling.

---

## Dedicated CPU

Dedicated CPU provides exclusive physical execution resources to a Compute Unit.

For example:

```text
Dedicated Pool

CPU 0  ─┐
CPU 1   │
CPU 2   ├── CU-A
CPU 3  ─┘

CPU 4  ─┐
CPU 5   │
CPU 6   ├── CU-B
CPU 7  ─┘
```

Once CPUs are assigned to CU-A, those same CPU resources must not simultaneously be assigned to another active Compute Unit.

Kloigos uses Linux CPU affinity and cgroup/cpuset mechanisms to enforce this boundary.

The architectural guarantee is exclusivity, not merely preferential scheduling.

### Dedicated Capacity Accounting

Dedicated CPU capacity is based on actual available physical execution resources.

If a host has 32 CPU units assigned to its Dedicated Pool and 24 are currently allocated:

```text
Dedicated physical capacity: 32
Allocated:                   24
Available:                    8
```

A request for 12 Dedicated CPUs cannot be satisfied on that host even if the Linux scheduler could technically run additional processes there.

Dedicated capacity is not overcommitted.

---

## Shared CPU

Shared CPU allows multiple Compute Units to execute within the same physical CPU pool.

For example:

```text
Shared CPU Pool
CPUs 32-63
     │
     ├── CU-C
     ├── CU-D
     ├── CU-E
     └── CU-F
```

Linux schedules runnable processes from these Compute Units across the shared pool.

Unlike Dedicated CPU, purchasing or requesting a Shared CPU does not imply ownership of a specific physical CPU.

Instead, it represents an entitlement to shared execution capacity.

This allows Kloigos to benefit from statistical multiplexing: workloads that are not simultaneously CPU-bound can share physical processors efficiently.

---

## Shared CPU Entitlement

The intended Shared CPU model is primarily **burstable**.

A Compute Unit receives a proportional entitlement under contention but may consume additional otherwise-unused capacity when the Shared Pool is idle.

Conceptually:

```text
No contention

CU-A entitlement: 2
CU-B entitlement: 2

CU-A busy
CU-B idle

        ↓

CU-A may use additional idle
Shared Pool capacity
```

Under contention:

```text
CU-A busy
CU-B busy
CU-C busy

        ↓

Linux scheduler distributes
capacity according to their
relative entitlements
```

This is fundamentally different from enforcing a hard CPU execution ceiling at all times.

---

## CPU Weight

Linux cgroup v2 provides `cpu.weight`, exposed by systemd through controls such as `CPUWeight=`.

Kloigos can use relative CPU weights to represent Shared CPU entitlement.

Conceptually:

```text
CU-A: 1 Shared CPU
CU-B: 2 Shared CPUs
CU-C: 4 Shared CPUs

Relative entitlement:

CU-A   █
CU-B   ██
CU-C   ████
```

The exact numerical mapping between Kloigos Shared CPU units and Linux CPU weights is an implementation and validation concern.

The architectural requirement is that relative entitlements behave predictably under sustained contention.

Kloigos should not expose raw Linux scheduler weights as its user-facing resource model.

Users request Shared CPU capacity; Kloigos translates that request into appropriate Linux scheduling controls.

---

## CPU Quotas

Linux cgroup v2 also supports CPU bandwidth limits through `cpu.max`, commonly exposed through systemd as `CPUQuota=`.

CPU quotas can impose a hard maximum amount of CPU time over a scheduling period.

For example, a configuration equivalent to:

```text
CPUQuota=200%
```

can limit a workload to approximately two CPUs worth of execution time.

Quotas may be useful when Kloigos needs to enforce an explicit upper bound.

However, hard quota enforcement introduces throttling semantics that differ from the burstable Shared CPU model.

Therefore:

> **CPU weight is the primary mechanism for proportional Shared CPU entitlement. CPU quota is an optional mechanism for policies that explicitly require a hard execution ceiling.**

Kloigos should not introduce quota-based throttling into Shared CPU behavior accidentally.

---

## Shared CPU Overcommit

Shared CPU capacity may be exposed at a ratio greater than the number of physical CPUs in the Shared Pool.

For example:

```text
Shared Pool physical CPUs: 32
Configured overcommit:     2:1

Logical Shared CPU capacity: 64
```

Kloigos may therefore allocate up to 64 Shared CPU units from those 32 physical CPUs.

This does not mean 64 physical CPUs exist.

It means Kloigos permits logical CPU entitlements to exceed physical capacity because those workloads are expected to share execution time.

Overcommit is an administrator-controlled capacity policy.

It is not a property of Dedicated CPU.

---

## Physical and Logical Capacity

Kloigos must distinguish between physical Shared Pool capacity and logical allocatable Shared CPU capacity.

For example:

```text
Host CPU Capacity

Physical CPUs:                  64

Dedicated Pool:                 32 physical CPUs

Shared Pool:                    32 physical CPUs
Shared overcommit ratio:         2:1
Logical Shared CPU capacity:    64
```

Capacity reporting should not collapse these into a single misleading CPU number.

The control plane should be able to represent at least:

- Dedicated physical capacity
- Dedicated allocated capacity
- Shared physical capacity
- Shared logical capacity
- Shared logical allocated capacity

This distinction is important for scheduling, administration, metering, and troubleshooting.

---

## Pool Isolation

Dedicated and Shared CPU pools must not unintentionally overlap.

For example:

```text
CPUs 0-31
Dedicated Pool

CPUs 32-63
Shared Pool
```

A Shared Compute Unit must not execute on CPUs reserved for the Dedicated Pool.

Likewise, general Shared Pool workloads must not consume CPU resources promised exclusively to Dedicated Compute Units.

Linux cpuset boundaries provide a natural mechanism for enforcing this separation.

The exact CPU numbering is host-specific and must respect hardware topology.

---

## Dynamic Compute Unit Provisioning

CPU resources are allocated when Kloigos materializes a Compute Unit.

For Dedicated CPU:

```text
Allocation requests 4 Dedicated CPUs
        ↓
Scheduler selects host
        ↓
Reserve 4 suitable CPUs
        ↓
Create CU cpuset
        ↓
Materialize enforcement
        ↓
Activate Allocation
```

For Shared CPU:

```text
Allocation requests 4 Shared CPUs
        ↓
Scheduler selects host with
logical Shared capacity
        ↓
Reserve 4 logical Shared units
        ↓
Place CU in Shared Pool
        ↓
Configure scheduling entitlement
        ↓
Activate Allocation
```

The Compute Unit does not need to exist before the request.

CPU configuration is part of CU materialization.

Detailed reservation and rollback behavior belongs in the **Dynamic Compute Unit Provisioning** design.

---

## CPU Topology

Logical CPU identifiers do not necessarily represent equivalent independent physical resources.

Modern systems may include:

- multiple sockets
- multiple NUMA nodes
- physical cores
- simultaneous multithreading (SMT) siblings
- heterogeneous core types

Kloigos must therefore understand enough host topology to avoid making incorrect exclusivity claims.

For example:

```text
Physical Core 0
    ├── CPU 0
    └── CPU 1
```

If CPU 0 and CPU 1 are SMT siblings, assigning them independently to unrelated Dedicated Compute Units may provide different isolation characteristics from assigning complete physical cores.

The administrator-facing and user-facing meaning of a "Dedicated CPU" must therefore correspond to the topology policy Kloigos actually enforces.

Kloigos should not assume that Linux logical CPU IDs are always equivalent to independent physical cores.

---

## NUMA Awareness

On multi-socket and NUMA systems, CPU placement affects memory locality and performance.

For example:

```text
NUMA Node 0
├── CPUs 0-31
└── Local Memory

NUMA Node 1
├── CPUs 32-63
└── Local Memory
```

Where practical, Kloigos should construct CPU pools and Dedicated CPU assignments that respect NUMA topology.

A large Compute Unit should preferably receive a coherent CPU set rather than an arbitrary collection of CPU IDs scattered across the machine.

CPU placement may also influence memory placement.

Detailed cross-resource placement policy belongs in the **Scheduling and Placement Model** design.

---

## Fragmentation

Dynamic Dedicated CPU allocation can create fragmentation.

For example, a host may have eight unallocated CPUs but lack a suitable contiguous or topology-compatible group of eight CPUs for a particular request.

Therefore:

```text
total free CPU
```

is not always equivalent to:

```text
CPU capacity capable of
satisfying this request
```

Initial scheduling may prioritize correctness and topology safety over sophisticated optimization.

More advanced fragmentation-aware placement can evolve later without changing the fundamental CPU model.

---

## Resource Changes

Changing an Allocation's CPU configuration may require changing its Compute Unit.

For example:

```text
Allocation A

4 Dedicated CPUs
       │
       ▼
CU-1

resize to

8 Dedicated CPUs
       │
       ▼
CU-2
```

Kloigos may construct a replacement Compute Unit rather than attempting to mutate every execution boundary in place.

The Allocation remains the durable workload identity.

Whether particular CPU changes can be performed in place is an implementation decision and must not weaken resource guarantees.

---

## Metering

CPU metering is based on allocated resources rather than measured CPU utilization.

For example:

```text
Allocation A
4 Dedicated CPUs
10 hours
```

is metered as four Dedicated CPUs for ten hours regardless of whether the workload used those CPUs continuously.

Likewise:

```text
Allocation B
4 Shared CPUs
10 hours
```

is metered according to four allocated Shared CPU units, not according to accumulated scheduler runtime.

Dedicated and Shared CPU may have different administrator-defined prices because they provide different resource guarantees.

Detailed accounting behavior belongs in the **Metering and Pricing Model** design.

---

## Failure and Cleanup

CPU reservation participates in the overall Compute Unit provisioning transaction.

For example:

```text
Reserve Dedicated CPUs
        ↓
Reserve Memory
        ↓
Reserve IP
        ↓
Storage provisioning FAILED
```

The reserved CPUs must be returned safely to the host's available capacity.

A CPU must not become available for another Compute Unit while stale host configuration still permits the previous CU to execute on it.

Likewise, Shared CPU logical capacity must be returned when provisioning fails or the Compute Unit is destroyed.

---

## Reconciliation

Kloigos must be able to compare control-plane CPU assignments with actual Linux host state.

For example:

```text
Control Plane

CU-A → CPUs 4-7
        │
        │ compare
        ▼
Linux Host

cpuset / cgroup / systemd state
```

A database record claiming exclusive CPU ownership is insufficient if Linux does not enforce the corresponding boundary.

Unexpected divergence must be detectable and recoverable.

---

## Validation Requirements

CPU guarantees must be validated on real physical hosts.

Validation should include at minimum:

### Dedicated CPU

- requested CPU count
- correct cpuset assignment
- exclusivity between Compute Units
- separation from Shared Pool CPUs
- topology policy
- NUMA placement where applicable
- capacity exhaustion
- release after teardown
- cleanup after failed provisioning
- concurrent reservation safety

### Shared CPU

- execution restricted to Shared Pool CPUs
- logical capacity accounting
- configured overcommit policy
- relative entitlement under contention
- ability to consume idle capacity where burstable behavior is expected
- optional hard caps where explicitly configured
- capacity release after teardown

### Contention

Tests should create real CPU pressure across multiple Compute Units.

Configuration inspection alone is insufficient.

Kloigos must demonstrate that the Linux scheduler and cgroup configuration produce the resource behavior promised by the control plane.

Detailed test execution belongs in the **Validation Architecture** design.

---

## Architectural Invariants

The Kloigos CPU model is governed by the following invariants:

1. **Dedicated CPU and Shared CPU are distinct resource types with different guarantees.**

2. **Dedicated CPU provides exclusive CPU execution resources and must not be silently overcommitted.**

3. **The same Dedicated CPU resource must not simultaneously belong to multiple active Compute Units.**

4. **Shared CPU uses an explicitly defined physical Shared Pool.**

5. **Shared Compute Units must not consume CPUs reserved for the Dedicated Pool.**

6. **Shared CPU may be logically overcommitted only according to administrator-defined policy.**

7. **Physical Shared CPU capacity and logical Shared CPU capacity must remain distinguishable.**

8. **Shared CPU entitlement should primarily use proportional scheduling and permit bursting into unused Shared Pool capacity unless a policy explicitly defines a hard cap.**

9. **Hard CPU quotas must not be introduced in a way that silently changes Shared CPU semantics.**

10. **Kloigos must account for hardware topology when making CPU isolation guarantees.**

11. **NUMA and CPU topology may constrain whether apparently free CPU capacity can satisfy a request.**

12. **CPU reservations must be concurrency-safe.**

13. **Failed provisioning and CU teardown must return CPU capacity without leaving stale execution access.**

14. **Control-plane CPU assignments must correspond to actual Linux enforcement.**

15. **CPU metering is based on allocated capacity, not instantaneous CPU utilization.**

---

## Open Design Areas

Several details intentionally remain subject to implementation and validation:

- the exact user-facing definition of a Dedicated CPU on SMT-enabled hardware
- the mapping between Shared CPU units and `cpu.weight`
- default Shared CPU overcommit ratios
- whether overcommit is configured globally, per Host Family, per Instance Class, or per host
- whether Shared CPU offerings support optional hard caps
- exact NUMA placement policy
- fragmentation-aware scheduling strategy
- behavior on heterogeneous CPU architectures

These decisions should be made through measurement and validation rather than encoded prematurely into the architectural model.

They may refine the implementation without changing the fundamental distinction between Dedicated and Shared CPU.

---

## Related Design Documents

This document defines CPU resource semantics.

Related behavior is defined in:

- **Compute Unit and Allocation Model** — CPU enforcement as part of the Compute Unit and CPU resource intent as part of the Allocation.
- **Dynamic Compute Unit Provisioning** — runtime CPU reservation, CU materialization, teardown, and rollback.
- **Scheduling and Placement Model** — CPU availability, topology, NUMA, fragmentation, and host selection.
- **Metering and Pricing Model** — accounting and pricing for Dedicated and Shared CPU.
- **Security and Isolation Model** — CPU isolation as part of the Compute Unit boundary.
- **Validation Architecture** — contention testing and verification of actual CPU enforcement.

The central CPU principle is:

> **Dedicated CPU reserves physical execution capacity. Shared CPU deliberately multiplexes a controlled physical pool. The distinction is explicit throughout scheduling, enforcement, capacity reporting, and metering.**
