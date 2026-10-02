# Storage and Persistence Model

## Purpose

Kloigos separates durable workload storage from the Compute Unit that currently executes the workload.

The core principle is:

> **Persistent storage belongs to the Allocation. A Compute Unit only provides the current host-side realization and attachment of that storage.**

This follows the broader Kloigos architecture:

> **Hosts provide capacity. Compute Units provide execution boundaries. Allocations provide durable workload identity.**

A Compute Unit may be destroyed, replaced, resized, or moved without inherently destroying the persistent data belonging to its Allocation.

This document defines storage ownership, physical realization, lifecycle, isolation, capacity management, and the relationship between storage, Allocations, Compute Units, and physical hosts.

Detailed scheduling, provisioning, security, and metering behavior belongs in their respective design documents.

---

## Storage Model

At a high level:

```text
Physical Host
     │
     │ provides storage capacity
     ▼
Storage Pool
     │
     │ allocates
     ▼
Persistent Storage
     │
     │ logically belongs to
     ▼
Allocation
     │
     │ attached through
     ▼
Compute Unit
     │
     ▼
User Workload
```

The physical host provides storage capacity.

Kloigos allocates storage from that capacity and associates the resulting persistent storage identity with an Allocation.

The Compute Unit makes that storage accessible to the workload while the Allocation executes on the host.

The distinction between ownership and attachment is fundamental.

---

## Logical Ownership and Physical Realization

Persistent storage has two related but separate aspects.

### Logical Storage

The Allocation owns or references the durable storage identity.

This may include:

- storage identifier
- requested capacity
- storage class or characteristics
- filesystem identity
- ownership information
- lifecycle policy
- metering history
- current physical location

### Physical Realization

The physical host provides the actual storage implementation.

For example:

```text
Allocation A
    │
    └── Persistent Storage A
              │
              │ realized as
              ▼
         LVM Logical Volume
              │
              │ attached to
              ▼
            CU-17
              │
              ▼
            Host-3
```

The exact host-side implementation may evolve without changing the logical ownership model.

---

## LVM

Kloigos may use Linux Logical Volume Manager (LVM) as the primary mechanism for dynamically allocating local persistent storage.

Conceptually:

```text
Physical Disks
      │
      ▼
LVM Physical Volumes
      │
      ▼
Volume Group
      │
      ├── Allocation A LV
      ├── Allocation B LV
      └── Free Capacity
```

LVM provides a natural mechanism for dividing physical storage capacity into independently managed logical volumes.

A logical volume can be:

- created
- sized
- formatted
- mounted
- unmounted
- extended
- removed

without requiring a predefined inventory of fixed storage shapes.

The use of LVM is an implementation choice consistent with the Kloigos Linux-native architecture.

The durable architectural principle is that storage is allocated from administrator-managed physical capacity and associated with an Allocation independently of its Compute Unit lifecycle.

---

## Storage Pools

Administrators make storage capacity available to Kloigos through storage pools.

A pool may represent capacity with particular characteristics, such as:

- physical host
- device type
- capacity
- performance characteristics
- redundancy characteristics
- storage class
- locality
- filesystem capabilities

Conceptually:

```text
Host-A

NVMe Pool
├── Allocation A
├── Allocation B
└── Free Capacity


Host-B

General Storage Pool
├── Allocation C
└── Free Capacity
```

The exact administrative schema may evolve.

The scheduler must understand enough about storage availability and locality to determine whether a host can satisfy an Allocation request.

---

## Storage Is a Schedulable Resource

Available storage capacity participates in placement decisions.

For example:

```text
Host-A

CPU:       available
Memory:    available
IP:        available
Storage:   insufficient

Result: host cannot satisfy request
```

Likewise, a host may have sufficient total free bytes but lack storage of the required class or characteristics.

Storage therefore participates in multidimensional capacity evaluation alongside CPU, memory, networking, tenancy, and other resources.

Detailed host-selection behavior belongs in the **Scheduling and Placement Model** design.

---

## Persistent Storage and Compute Units

A Compute Unit does not own persistent storage simply because the storage is currently mounted there.

For example:

```text
Allocation A
    │
    └── Storage A
           │
           ▼
         CU-1
           │
           ▼
        Host-A
```

If CU-1 is replaced:

```text
Allocation A
    │
    └── Storage A
           │
           ▼
         CU-2
           │
           ▼
        Host-A
```

Storage A remains part of Allocation A.

The old Compute Unit is destroyed.

The storage is reattached or remounted through the replacement Compute Unit.

This separation enables Compute Unit lifecycle operations without coupling them to destructive storage operations.

---

## Ephemeral and Persistent Storage

Kloigos may support storage with different lifecycle semantics.

### Persistent Storage

Persistent storage survives Compute Unit replacement.

Its lifecycle is associated with the Allocation or with an explicitly managed storage resource.

### Ephemeral Storage

Ephemeral storage may exist only for the lifetime of a particular Compute Unit.

For example:

```text
Compute Unit
├── persistent Allocation storage
└── ephemeral execution storage
```

Destroying the CU may safely destroy its ephemeral storage.

The lifecycle distinction must be explicit.

Kloigos must never infer that storage is disposable merely because the Compute Unit using it is being destroyed.

---

## Filesystem Ownership

Storage isolation depends on Linux filesystem ownership and permissions.

When persistent storage is attached to a Compute Unit, the workload must receive access appropriate to the Allocation's Unix identity.

Another Compute Unit sharing the physical host must not gain access merely because the underlying storage resides on the same server.

Conceptually:

```text
Storage A
Owner: Allocation A
        │
        ▼
      CU-A
        ✓


      CU-B
        ✗
```

Filesystem ownership must remain consistent across Compute Unit replacement.

If Unix identity is durable across the Allocation lifecycle, storage ownership should remain compatible with that identity.

Detailed identity and security guarantees belong in the **Security and Isolation Model** design.

---

## Storage Provisioning

Storage provisioning occurs as part of the overall Allocation and Compute Unit provisioning process.

Conceptually:

```text
Allocation Request
        │
        ▼
Determine Storage Requirements
        │
        ▼
Select Compatible Host
        │
        ▼
Reserve Storage Capacity
        │
        ▼
Create / Assign Storage
        │
        ▼
Configure Filesystem
        │
        ▼
Attach to Compute Unit
        │
        ▼
Set Ownership and Permissions
        │
        ▼
Activate Allocation
```

Storage reservation must be concurrency-safe.

Two simultaneous requests must not successfully consume the same exclusive capacity.

The Allocation must not become ACTIVE until the required storage is correctly available to its Compute Unit.

---

## Storage Lifecycle

A simplified persistent storage lifecycle may resemble:

```text
AVAILABLE CAPACITY
        │
        │ reserve
        ▼
RESERVED
        │
        │ materialize
        ▼
PROVISIONED
        │
        │ attach
        ▼
ATTACHED
        │
        │ CU replacement
        ▼
DETACHED
        │
        │ attach to replacement CU
        └──────────────► ATTACHED

        │
        │ Allocation/storage deletion
        ▼
DELETING
        │
        ▼
CAPACITY RETURNED
```

The exact state machine may evolve.

The important distinction is that **detaching storage from a Compute Unit is not equivalent to deleting the storage**.

---

## Compute Unit Teardown

When a Compute Unit is destroyed, Kloigos must determine which resources are execution resources and which are durable Allocation resources.

Conceptually:

```text
Destroy Compute Unit
        │
        ├── remove cgroup
        ├── release CPU
        ├── remove network realization
        ├── remove temporary state
        │
        └── detach persistent storage
                  │
                  ▼
             PRESERVE DATA
```

Persistent storage must not be deleted as an incidental side effect of Compute Unit teardown.

Destructive storage operations require an explicit lifecycle decision associated with the Allocation or storage resource.

---

## Allocation Termination

Allocation termination and storage deletion are related but should not be unnecessarily conflated.

Kloigos may support policies such as:

```text
Allocation Terminated
        │
        ├── delete associated storage
        │
        └── retain associated storage
```

The exact product policy may evolve.

The architectural requirement is that storage destruction is deliberate and explicit.

A failed CU cleanup operation must never accidentally become a persistent-data deletion operation.

---

## Resizing Storage

Persistent storage may need to grow during an Allocation's lifetime.

For example:

```text
Storage A

100 GB
   │
   │ resize
   ▼
250 GB
```

Where supported by the underlying storage and filesystem, Kloigos may extend storage without replacing the Allocation.

Storage reduction is substantially more complex because filesystems and stored data may not safely shrink.

Kloigos should not assume that increasing and decreasing storage have equivalent semantics.

Exact resize capabilities should be defined by the supported storage implementation and exposed accurately to users.

---

## Locality

Local physical storage introduces placement constraints.

For example:

```text
Allocation A
     │
     └── Storage A
              │
              ▼
           Host-A
```

If Storage A physically resides on Host-A, moving the Allocation to Host-B requires the data to become available there.

This may require:

- copying the data
- replicating the data
- restoring from another source
- using shared or network-accessible storage
- restricting placement to Host-A

Kloigos must not treat local storage as transparently portable when the underlying infrastructure does not provide that capability.

---

## Placement and Migration

Storage locality is therefore a first-class placement constraint.

A future placement transition may resemble:

```text
Allocation A
     │
     └── Storage A
              │
              ▼
            CU-1
              │
              ▼
           Host-A

        migration

Storage A copied / made available
              │
              ▼
            CU-2
              │
              ▼
           Host-B
```

Only after the destination storage is valid and consistent can the Allocation safely depend on it.

The architecture does not require transparent live storage migration.

A workload may need to stop or restart as part of a placement transition.

The important principle is:

> **Allocation identity can survive a placement change even when the physical realization of its storage must change.**

---

## Storage Performance

Storage capacity alone may not fully describe a storage resource.

Different physical infrastructure may provide different:

- throughput
- IOPS
- latency
- device types
- redundancy characteristics

Instance Classes or future storage classes may expose meaningful distinctions without requiring application users to understand specific physical devices.

For example:

```text
User Request

high-performance storage
        │
        ▼
Kloigos policy
        │
        ▼
Eligible storage pools
        │
        ▼
NVMe-backed capacity
```

Kloigos should expose guarantees only when the underlying infrastructure and enforcement model can actually support them.

---

## I/O Resource Controls

Linux cgroups can provide I/O controls for supported block devices.

Kloigos may use these mechanisms to enforce storage performance limits or relative priorities.

However, storage performance isolation depends heavily on the underlying device and workload characteristics.

Therefore, performance guarantees must be validated empirically.

The existence of an I/O control configuration does not by itself prove that a particular latency, throughput, or IOPS guarantee is achievable.

---

## Capacity Accounting

Kloigos must track storage capacity that is:

- physically available
- reserved
- provisioned
- attached
- reclaimable

For example:

```text
Storage Pool

Physical capacity:    4 TB
Provisioned:           2 TB
Reserved:            500 GB
Available:           1.5 TB
```

Capacity accounting must reflect the actual allocation behavior of the underlying storage technology.

If thin provisioning is introduced in the future, logical and physical capacity must be reported separately rather than presenting overcommitted logical capacity as physical free space.

---

## Failure and Rollback

Storage provisioning participates in the overall Compute Unit provisioning transaction.

For example:

```text
Reserve CPU
    ↓
Reserve Memory
    ↓
Reserve IP
    ↓
Reserve Storage
    ↓
Create Logical Volume
    ↓
Configure Filesystem
    ↓
Network Configuration FAILED
```

Kloigos must distinguish between storage created specifically for the failed request and durable storage that existed before the provisioning attempt.

New temporary resources may need to be removed.

Existing durable storage must not be destroyed.

This distinction is especially important during Compute Unit replacement, recovery, and migration.

---

## Safe Deletion

Persistent-data deletion is one of the most destructive operations Kloigos can perform.

Deletion must therefore be explicit and associated with the correct resource identity.

Conceptually:

```text
Compute Unit deletion
        ≠
Persistent storage deletion
```

Before returning storage capacity for reuse, Kloigos must ensure that:

- the old filesystem is no longer attached
- stale mounts are removed
- old ownership does not remain accessible
- the storage resource has entered the intended deletion lifecycle
- control-plane state agrees that the resource may be destroyed

Future security requirements may also define sanitization behavior before storage is reassigned to another Allocation.

---

## Reconciliation

The control plane records intended storage state.

The physical host contains actual storage state.

For example:

```text
Control Plane

Storage A
├── Allocation A
├── 100 GB
└── attached to CU-7
          │
          │ compare
          ▼
Physical Host

LVM state
filesystem
mount state
ownership
capacity
```

Kloigos should be able to detect meaningful divergence between these states.

Examples include:

- missing logical volume
- unexpected logical volume
- incorrect size
- incorrect mount
- incorrect ownership
- storage attached to the wrong Compute Unit
- control-plane capacity inconsistent with physical capacity

A database record alone is not proof that durable storage exists or is correctly isolated.

---

## Metering

Persistent storage is metered according to allocated capacity and allocation duration rather than bytes actively read or written.

For example:

```text
Allocation A
Storage: 500 GB
Duration: 30 days
```

is metered as 500 GB of allocated storage for the applicable period.

Storage class or performance characteristics may influence administrator-defined pricing.

If storage capacity changes during the Allocation lifetime, metering should preserve the historical periods during which each capacity level applied.

Detailed behavior belongs in the **Metering and Pricing Model** design.

---

## Validation Requirements

Storage guarantees must be validated on real hosts.

Validation should include at minimum:

### Provisioning

- requested storage capacity
- correct storage pool selection
- LVM creation where applicable
- filesystem creation
- correct mount
- correct ownership and permissions

### Isolation

- another Compute Unit cannot access the storage
- filesystem ownership remains correct
- protected host storage remains inaccessible

### Lifecycle

- persistent storage survives CU replacement
- CU teardown detaches but does not delete persistent storage
- explicit storage deletion returns capacity
- ephemeral storage is removed according to policy

### Capacity

- available capacity decreases after reservation
- capacity returns after deletion
- exhaustion fails cleanly
- concurrent reservations cannot oversubscribe exclusive capacity

### Failure

- failed provisioning cleans up newly created temporary resources
- failed CU replacement does not destroy existing persistent data
- interrupted cleanup remains detectable and recoverable

### Performance

Where performance controls are offered:

- throughput behavior
- IOPS behavior
- contention between Compute Units
- configured I/O limits or weights

Detailed execution belongs in the **Validation Architecture** design.

---

## Architectural Invariants

The Kloigos storage model is governed by the following invariants:

1. **Persistent storage is logically owned by the Allocation rather than the Compute Unit.**

2. **A Compute Unit provides the current physical attachment and execution-time access to persistent storage.**

3. **Destroying or replacing a Compute Unit must not inherently destroy persistent Allocation storage.**

4. **Storage deletion must be an explicit lifecycle operation rather than an incidental consequence of CU teardown.**

5. **Storage capacity is a schedulable infrastructure resource.**

6. **Storage reservation must be concurrency-safe.**

7. **Kloigos must respect storage locality when selecting or changing physical placement.**

8. **Local storage must not be represented as transparently portable when the underlying infrastructure does not provide portability.**

9. **Filesystem ownership and permissions must prevent unauthorized Compute Units from accessing another Allocation's storage.**

10. **Persistent storage identity must survive Compute Unit replacement where the storage lifecycle requires persistence.**

11. **Failed provisioning must distinguish newly created temporary storage from pre-existing durable storage.**

12. **Provisioning rollback must never destroy pre-existing persistent data merely because Compute Unit creation failed.**

13. **Control-plane storage state must correspond to actual host storage, filesystem, mount, and ownership state.**

14. **Storage performance guarantees must correspond to behavior that the underlying infrastructure can enforce and validate.**

15. **Storage metering is based on allocated capacity and duration rather than instantaneous I/O utilization.**

16. **Logical and physical capacity must remain distinguishable if storage overcommit or thin provisioning is introduced.**

---

## Open Design Areas

Several storage capabilities may evolve without changing the fundamental model:

- storage classes
- administrator pool configuration
- filesystem selection
- storage resize policy
- snapshots
- backups
- replication
- cross-host storage migration
- shared or network-attached storage
- thin provisioning
- storage sanitization policy
- IOPS and throughput guarantees
- storage redundancy
- recovery after physical disk failure

These capabilities should preserve the fundamental separation between durable Allocation storage and replaceable Compute Unit execution state.

---

## Related Design Documents

This document defines storage 
