# Tenancy Model

## Purpose

Kloigos allows organizations to choose whether physical servers are shared with other organizations or reserved exclusively for their workloads.

The tenancy model operates at the **physical host boundary**.

Kloigos supports two primary tenancy modes:

- **Shared Tenancy** — Compute Units belonging to different organizations may run on the same physical host.
- **Dedicated Server Tenancy** — a physical host is reserved for a single organization and no Compute Units belonging to another organization may be placed on it.

The core principle is:

> **Tenancy determines who may share a physical host. Compute Unit isolation determines how workloads are separated within that host.**

Dedicated Server Tenancy does not create a different Compute Unit implementation. It changes the placement and capacity rules governing which organizations may use the physical server.

This document defines tenancy ownership, scheduling constraints, host lifecycle, isolation implications, and the architectural invariants of the Kloigos tenancy model.

---

## Tenancy Boundary

Kloigos Compute Units share the Linux kernel of their physical host.

Under Shared Tenancy:

```text
Physical Host
┌───────────────────────────────────────────┐
│               Linux Kernel                │
│                                           │
│   Organization A       Organization B     │
│                                           │
│   ┌───────────┐        ┌───────────┐      │
│   │   CU-A1   │        │   CU-B1   │      │
│   └───────────┘        └───────────┘      │
│                                           │
│   ┌───────────┐        ┌───────────┐      │
│   │   CU-A2   │        │   CU-B2   │      │
│   └───────────┘        └───────────┘      │
│                                           │
└───────────────────────────────────────────┘
```

Under Dedicated Server Tenancy:

```text
Physical Host
┌───────────────────────────────────────────┐
│               Linux Kernel                │
│                                           │
│             Organization A                │
│                                           │
│   ┌───────────┐        ┌───────────┐      │
│   │   CU-A1   │        │   CU-A2   │      │
│   └───────────┘        └───────────┘      │
│                                           │
│   ┌───────────┐                           │
│   │   CU-A3   │       Free Capacity       │
│   └───────────┘                           │
│                                           │
└───────────────────────────────────────────┘

Organization B cannot use this host.
```

The remaining unused capacity belongs to the dedicated tenancy reservation and cannot be consumed by another organization.

---

## Organization as the Tenancy Owner

Tenancy is evaluated at the organization boundary.

Multiple Allocations belonging to the same organization may share a dedicated physical host.

For example:

```text
Organization A
      │
      ├── Allocation A1
      ├── Allocation A2
      └── Allocation A3
              │
              ▼
       Dedicated Host
```

The dedicated host is not necessarily dedicated to one Allocation.

It is dedicated to one organization.

This distinction allows an organization to efficiently use the capacity of its reserved physical servers while preventing cross-organization sharing.

---

## Shared Tenancy

Shared Tenancy allows Kloigos to place Allocations from different organizations on the same physical host.

For example:

```text
Host-1

Organization A
├── CU-A1
└── CU-A2

Organization B
└── CU-B1

Organization C
└── CU-C1
```

Each Compute Unit still receives its normal resource and security boundaries.

These may include:

- Linux identity
- CPU controls
- memory controls
- filesystem ownership
- storage isolation
- network identity
- nftables enforcement
- AppArmor policy

Shared Tenancy therefore depends on the standard Kloigos Compute Unit isolation model.

Detailed enforcement belongs in the **Security and Isolation Model** design.

---

## Dedicated Server Tenancy

Dedicated Server Tenancy prevents workloads from other organizations from sharing the physical server.

For example:

```text
Host-7
Tenancy Owner: Organization A

Allowed:

Organization A / Allocation A1
Organization A / Allocation A2
Organization A / Allocation A3

Not Allowed:

Organization B / Allocation B1
Organization C / Allocation C1
```

This restriction applies regardless of how much unused capacity remains on the host.

For example:

```text
Host-7

Total CPU:       64
Allocated:       16
Unused:          48

Tenancy Owner: Organization A
```

The remaining 48 CPUs cannot be allocated to Organization B while the dedicated tenancy reservation remains active.

This is intentional stranded capacity created by the tenancy guarantee.

---

## Why Dedicated Tenancy Exists

Compute Units on a Kloigos host share the host Linux kernel.

Shared Tenancy therefore means organizations share a kernel even though their individual workloads are isolated using Linux security and resource-control mechanisms.

Dedicated Server Tenancy changes that exposure:

```text
Shared Tenancy

Org A ─┐
Org B ─┼── shared kernel
Org C ─┘


Dedicated Tenancy

Org A ─── shared kernel

No other organization
shares that kernel
```

Dedicated Server Tenancy therefore limits the kernel-sharing boundary to workloads belonging to the same organization.

It does not provide:

- separate kernels between Compute Units
- VM-style isolation
- protection from the physical-host administrator
- protection between mutually hostile workloads inside the same organization

It provides an **organization-level physical-host exclusivity guarantee**.

---

## Tenancy as a Scheduling Constraint

Tenancy is a first-class placement constraint.

Before selecting a host, the scheduler must determine whether the requested Allocation is compatible with the host's current tenancy state.

Conceptually:

```text
Allocation Request
        │
        ├── Organization
        ├── Tenancy Mode
        └── Resource Requirements
                │
                ▼
          Candidate Hosts
                │
                ▼
          Tenancy Filter
                │
                ▼
         Capacity Evaluation
                │
                ▼
           Host Selection
```

A host with sufficient CPU, memory, storage, and IP capacity may still be ineligible because of tenancy.

---

## Host Tenancy State

A physical host may conceptually exist in states such as:

```text
SHARED
```

or:

```text
DEDICATED
Owner: Organization A
```

A host may also need transitional states while becoming dedicated or returning to shared service.

For example:

```text
SHARED
   │
   │ reserve for Organization A
   ▼
DRAINING
   │
   │ incompatible Allocations removed
   ▼
DEDICATED
Owner: Organization A
```

and later:

```text
DEDICATED
Owner: Organization A
   │
   │ release tenancy
   ▼
CLEANUP
   │
   │ host verified reusable
   ▼
SHARED
```

The exact state machine may evolve.

The architectural requirement is that transitions never temporarily violate the tenancy guarantee.

---

## Acquiring a Dedicated Host

A host can become dedicated to an organization only when no incompatible Allocations remain on it.

For example:

```text
Host-3

Org A CU
Org B CU
Org C CU
```

Host-3 cannot immediately become dedicated to Organization A.

Kloigos must either:

- choose another eligible host
- wait for incompatible Allocations to terminate
- move incompatible Allocations elsewhere
- explicitly drain the host through a supported administrative workflow

Kloigos must never simply mark the host dedicated while another organization's workload remains active.

---

## Existing Dedicated Hosts

If an organization already owns a dedicated host with sufficient compatible capacity, additional Allocations from that organization may be placed there.

For example:

```text
Allocation Request
Organization: A
Tenancy: DEDICATED
CPU: 8

        │
        ▼

Host-7
Dedicated to Organization A
Available CPU: 16

        │
        ▼

Eligible
```

This allows an organization to consume the reserved server incrementally rather than requiring one Allocation to consume the entire machine.

---

## Dedicated Tenancy and Dynamic Compute Units

Dedicated Server Tenancy does not require pre-created Compute Units.

The physical host remains the owner of allocatable capacity.

For example:

```text
Dedicated Host
Organization A
       │
       ├── free CPU
       ├── free memory
       ├── free storage
       └── compatible IP capacity
              │
              ▼
      Allocation Request
              │
              ▼
       Reserve Resources
              │
              ▼
      Materialize Compute Unit
```

The normal Dynamic Compute Unit Provisioning model remains unchanged.

The difference is that only requests belonging to the tenancy owner may consume the host's capacity.

---

## Dedicated Tenancy and CPU Models

Dedicated Server Tenancy is independent from Dedicated CPU.

These concepts must not be confused.

For example, an Allocation may request:

```text
Tenancy: Dedicated Server
CPU: Shared CPU
```

This means:

- the physical host is exclusive to the organization
- CPUs may still be shared among that organization's Compute Units

Likewise:

```text
Tenancy: Shared Server
CPU: Dedicated CPU
```

means:

- the Allocation receives exclusive CPU resources
- other organizations may still use different resources on the same physical host

The dimensions are independent:

| Server Tenancy | CPU Model | Meaning |
|---|---|---|
| Shared | Shared | Host and CPU pool may both be shared |
| Shared | Dedicated | CPU resources exclusive; host may contain other organizations |
| Dedicated | Shared | Host exclusive to organization; CPU capacity may be shared within it |
| Dedicated | Dedicated | Host exclusive to organization and assigned CPU resources exclusive to CU |

This distinction must remain explicit in the API, scheduling logic, capacity reporting, and metering.

---

## Dedicated Tenancy and Storage

Dedicated tenancy applies to the physical host, not automatically to external infrastructure.

If persistent storage resides locally on the dedicated host, that storage naturally resides within the same physical-host tenancy boundary.

If Kloigos later supports shared or network-attached storage, Dedicated Server Tenancy does not automatically imply that the external storage infrastructure is physically dedicated.

Any stronger storage-tenancy guarantee must be explicitly defined by the storage model.

---

## Dedicated Tenancy and Networking

Dedicated Server Tenancy does not inherently provide a dedicated physical network.

Allocation IPs continue to come from administrator-configured compatible IP pools.

Network Security Groups and host-level network enforcement continue to apply.

If dedicated NICs, VLANs, or network infrastructure are offered in the future, those are separate infrastructure capabilities and must not be implied merely by `tenancy=DEDICATED`.

---

## Tenancy Reservation

Dedicated tenancy consumes the entire host from the perspective of cross-organization scheduling.

For example:

```text
Host Capacity

CPU:       64
Memory:    512 GB
Storage:   4 TB

Organization A usage:

CPU:       16
Memory:    64 GB
Storage:   500 GB
```

Although substantial physical capacity remains unused, that capacity is unavailable to other organizations.

Capacity reporting should distinguish between:

- physically unused capacity
- capacity available to the tenancy owner
- capacity available to the general shared fleet

This prevents the control plane from reporting dedicated but unused capacity as generally schedulable.

---

## Tenancy Lifecycle

Dedicated tenancy has a lifecycle separate from individual Compute Units.

For example:

```text
Host-7
Dedicated to Organization A

    │
    ├── CU-A1 created
    ├── CU-A2 created
    ├── CU-A1 destroyed
    └── CU-A2 destroyed
```

The destruction of the last Compute Unit does not necessarily mean that the host immediately becomes shared.

The host's tenancy reservation may remain active independently of its current Allocation count.

This distinction is important because:

```text
No active CUs
```

does not necessarily mean:

```text
No tenancy owner
```

The exact product policy governing when dedicated tenancy is released may evolve.

---

## Releasing Dedicated Tenancy

Before a dedicated host can return to shared service, Kloigos must ensure that organization-specific execution state no longer creates unintended access or isolation problems.

Cleanup may include verifying:

- no active Compute Units remain
- no organization-specific CPU reservations remain
- temporary filesystem state is removed
- network configuration is cleaned up
- nftables rules are removed
- temporary mounts are removed
- security-policy associations are removed
- persistent storage is safely detached
- host capacity is reconciled

Persistent Allocation storage must not be destroyed merely because dedicated tenancy ends.

The host can return to the shared pool only after the transition is complete.

---

## Concurrency

Tenancy reservations must be concurrency-safe.

Consider two simultaneous requests:

```text
Request A
Organization A
Dedicated Tenancy

Request B
Organization B
Dedicated Tenancy

        │
        ▼

Same currently free Host-9
```

Both requests must not successfully acquire Host-9.

Likewise, a Shared Tenancy request must not race with a Dedicated Tenancy reservation and become active on the host after exclusivity has been granted.

Host tenancy state must therefore participate in the same atomic reservation model as other exclusive infrastructure resources.

---

## Failure and Rollback

Tenancy transitions may fail after partial work.

For example:

```text
Reserve Host
     ↓
Mark Dedicated
     ↓
Reserve CPU
     ↓
Reserve IP
     ↓
CU provisioning FAILED
```

Kloigos must determine whether the host tenancy reservation itself should remain or be rolled back according to the requested lifecycle.

It must never leave ambiguous state where the control plane considers a host shared while the host is still reserved for or contains state belonging to a dedicated tenant.

Likewise, a failed release operation must leave the host unavailable for incompatible placement until cleanup and reconciliation succeed.

Safety takes precedence over prematurely returning the host to the shared fleet.

---

## Metering

Dedicated Server Tenancy may carry a different price because the organization prevents other organizations from consuming unused capacity on the host.

For example:

```text
Physical Host
64 CPUs

Organization A
Dedicated Tenancy

Actual Allocation:
16 CPUs
```

Kloigos may need to account for the economic effect of reserving the physical server even though the Allocation consumes only part of its capacity.

The exact pricing model is administrator-defined and belongs in the **Metering and Pricing Model** design.

The tenancy model only establishes that dedicated capacity is unavailable to other organizations while the reservation is active.

---

## Reconciliation

The control plane must be able to determine whether actual host usage matches the intended tenancy state.

For example:

```text
Control Plane

Host-7
DEDICATED
Owner: Organization A
          │
          │ compare
          ▼
Actual Host State

CU-A1
CU-A2
CU-B1   ← violation
```

This is a critical isolation failure.

Reconciliation should be capable of detecting:

- foreign-organization Compute Units on dedicated hosts
- incorrect tenancy ownership
- stale tenancy reservations
- shared hosts incorrectly marked dedicated
- dedicated hosts incorrectly exposed as shared capacity

A database tenancy flag alone is not sufficient proof that the guarantee is being honored.

---

## Validation Requirements

Tenancy guarantees must be tested using real scheduling and provisioning behavior.

Validation should include at minimum:

### Shared Tenancy

- multiple organizations can share an eligible host
- normal Compute Unit isolation remains enforced
- capacity is correctly accounted across organizations

### Dedicated Tenancy

- first dedicated placement establishes correct organization ownership
- additional Allocations from the same organization may use the host
- Allocations from other organizations are rejected
- unused capacity is not exposed to other organizations
- multiple Compute Units from the owning organization can coexist

### CPU Independence

Validation should explicitly verify:

- Shared Host + Shared CPU
- Shared Host + Dedicated CPU
- Dedicated Host + Shared CPU
- Dedicated Host + Dedicated CPU

### Lifecycle

- destroying one CU does not release host tenancy
- destroying the final CU does not accidentally expose the host before tenancy policy allows it
- tenancy release performs required cleanup
- host can safely return to shared service

### Concurrency

- competing dedicated requests cannot acquire the same host
- shared placement cannot race into a host being reserved as dedicated
- host ownership changes are atomic

### Failure

- failed provisioning does not violate host ownership
- failed tenancy release keeps the host unavailable to incompatible organizations
- reconciliation detects invalid cross-organization placement

Detailed execution belongs in the **Validation Architecture** design.

---

## Architectural Invariants

The Kloigos tenancy model is governed by the following invariants:

1. **Tenancy is enforced at the physical-host boundary.**

2. **Shared Tenancy permits Allocations belonging to different organizations to share a physical host.**

3. **Dedicated Server Tenancy permits only Allocations belonging to the owning organization to use the physical host.**

4. **Unused capacity on a dedicated host must not be allocated to another organization.**

5. **A dedicated host may contain multiple Compute Units and Allocations belonging to its owning organization.**

6. **Dedicated Server Tenancy and Dedicated CPU are independent concepts.**

7. **Dedicated Server Tenancy does not imply dedicated networking, dedicated external storage, or separate kernels between Compute Units.**

8. **A host cannot become dedicated while incompatible Allocations remain active on it.**

9. **A host must not return to shared service until the dedicated tenancy has been safely released and required cleanup has completed.**

10. **Host tenancy reservations must be concurrency-safe.**

11. **A Shared Tenancy placement must not race with acquisition of Dedicated Server Tenancy.**

12. **The absence of active Compute Units does not inherently mean that a dedicated tenancy reservation has ended.**

13. **Dedicated tenancy must participate in scheduling before physical resources are committed to an incompatible placement.**

14. **Control-plane tenancy state must correspond to actual Allocation placement on the physical host.**

15. **Failure handling must prefer temporarily withholding a host from scheduling rather than risk violating its tenancy guarantee.**

16. **Dedicated Server Tenancy limits cross-organization kernel sharing but does not transform Compute Units into virtual machines.**

---

## Related Design Documents

This document defines organization-level physical-host sharing.

Related behavior is defined in:

- **Compute Unit and Allocation Model** — workload identity and execution placement.
- **Dynamic Compute Unit Provisioning** — host reservation and CU creation within the tenancy boundary.
- **Scheduling and Placement Model** — tenancy as a first-class host eligibility constraint.
- **CPU Resource Model** — Dedicated and Shared CPU independently of server tenancy.
- **Networking and IP Model** — network identity and isolation across Compute Units.
- **Storage and Persistence Model** — storage ownership and locality.
- **Security and Isolation Model** — implications of sharing the Linux kernel and the securi
