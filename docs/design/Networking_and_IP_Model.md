# Networking and IP Model

## Purpose

Kloigos provides Compute Units with native network connectivity using the physical host's Linux networking stack.

Kloigos does not require an overlay network, virtual router, or container networking layer. Instead, IP addresses supplied by the infrastructure administrator are allocated to workloads and configured on the physical host.

The core principle is:

> **IP addresses are administrator-provided infrastructure resources logically assigned to Allocations and enforced through the Compute Unit's host-native network boundary.**

This document defines the networking model, IP ownership and lifecycle, address pools, isolation boundaries, and the relationship between networking, Allocations, Compute Units, and physical hosts.

Detailed scheduling, security-group behavior, and Compute Unit provisioning are covered by their respective design documents.

---

## Network Model

At a high level:

```text
Physical Network
       │
       │ real network
       ▼
Physical Host NIC
       │
       ├── Host IP
       │
       ├── Allocation A IP
       │
       ├── Allocation B IP
       │
       └── Allocation C IP
               │
               ▼
        Linux Networking
               │
        nftables / policy
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

Each Allocation receives its own IP address.

That address comes from an administrator-configured IP pool and is usable on the physical network attached to the selected host.

The IP is not created by Kloigos from an internal overlay address space.

---

## Host-Native Networking

Kloigos intentionally uses standard Linux networking on the physical host.

An Allocation IP is configured as an additional real IP address associated with the host's network interface and then bound through Linux networking and firewall policy to the intended Compute Unit.

Conceptually:

```text
eth0
 │
 ├── 10.20.30.10     Host
 ├── 10.20.30.41     Allocation A
 ├── 10.20.30.42     Allocation B
 └── 10.20.30.43     Allocation C
```

The exact Linux mechanisms used to associate traffic with a Compute Unit may evolve.

The architectural requirement is that the network identity remains enforceable using host-native Linux facilities and does not depend on introducing a mandatory overlay network.

This keeps the network path close to ordinary bare-metal Linux networking and allows Kloigos workloads to participate directly in existing infrastructure networks.

---

## IP Pools

Kloigos does not invent network addresses.

Infrastructure administrators configure one or more pools containing IP addresses that Kloigos is permitted to allocate.

Conceptually:

```text
Administrator
     │
     ▼
IP Pool
10.20.30.40 - 10.20.30.99
     │
     ▼
Kloigos Control Plane
     │
     ├── .41 → Allocation A
     ├── .42 → Allocation B
     ├── .43 → Allocation C
     └── remaining addresses available
```

Pool configuration may include information necessary to determine where addresses are usable, such as:

- address range
- subnet
- network or VLAN identity
- gateway
- associated hosts or Host Families
- site or location
- address family

The exact pool schema belongs to the implementation and may evolve.

The architectural requirement is that Kloigos understands whether an address is compatible with the physical host selected for an Allocation.

---

## IP Addresses Are Schedulable Resources

An available IP address is part of infrastructure capacity.

A host with sufficient CPU, memory, and storage is not necessarily capable of satisfying an Allocation request if no compatible IP address is available.

For example:

```text
Host-A

CPU:       available
Memory:    available
Storage:   available
IP:        unavailable

Result: host cannot satisfy the request
```

Networking capacity therefore participates in placement decisions alongside other resources.

The scheduler must not select a host and only later discover that the required network identity cannot be provided when that constraint could have been known during scheduling.

Detailed multidimensional placement behavior belongs in the **Scheduling and Placement Model** design.

---

## Allocation and Compute Unit Responsibilities

Networking crosses the Allocation/Compute Unit boundary.

The Allocation owns the logical network identity.

The Compute Unit owns the host-side realization of that identity.

Conceptually:

```text
Allocation
    │
    └── IP identity: 10.20.30.41
                │
                ▼
          Compute Unit
                │
                ├── host IP configuration
                ├── traffic association
                └── nftables enforcement
```

This follows the broader Kloigos principle:

> **Durable identity belongs to the Allocation. Physical realization belongs to the Compute Unit.**

Destroying a Compute Unit therefore does not inherently mean that the Allocation must lose its network identity.

Whether a particular IP can remain unchanged across placement changes depends on the compatibility of the destination network.

---

## IP Allocation Lifecycle

A simplified IP lifecycle is:

```text
AVAILABLE
    │
    │ reserve
    ▼
RESERVED
    │
    │ provisioning succeeds
    ▼
ALLOCATED
    │
    │ Allocation terminates
    ▼
RELEASING
    │
    │ host state removed
    ▼
AVAILABLE
```

Reservation must be concurrency-safe.

Two simultaneous Allocation requests must never receive the same IP address.

An IP must not become available for reuse until Kloigos has safely removed the previous host-side configuration that could still receive or originate traffic using that address.

---

## Provisioning

Network provisioning occurs as part of Compute Unit materialization.

Conceptually:

```text
Select Host
     │
     ▼
Reserve IP
     │
     ▼
Create Compute Unit
     │
     ▼
Configure Host Networking
     │
     ▼
Apply Network Policy
     │
     ▼
Validate Configuration
     │
     ▼
Activate Allocation
```

An Allocation must not become ACTIVE merely because an IP exists in control-plane state.

The required host networking and enforcement must have been successfully materialized.

---

## Network Isolation

Because multiple Compute Units may share one physical Linux host, Kloigos must ensure that one Compute Unit cannot simply use another Allocation's network identity.

For example:

```text
Allocation A
10.20.30.41
      │
      ▼
    CU-A

Allocation B
10.20.30.42
      │
      ▼
    CU-B
```

CU-B must not be able to successfully impersonate `10.20.30.41` merely by attempting to originate traffic using that source address.

Kloigos uses host-level Linux networking and nftables enforcement to associate network traffic with the intended Compute Unit.

The exact rule structure may evolve, but enforcement of Allocation network identity is an architectural requirement.

---

## Network Security Groups

Kloigos may apply Network Security Groups (NSGs) to control permitted traffic for an Allocation or Compute Unit.

Conceptually:

```text
Physical Network
       │
       ▼
Allocation IP
       │
       ▼
Network Security Group
       │
       ▼
Compute Unit
       │
       ▼
Workload
```

NSGs are control-plane policy that is materialized using host networking mechanisms such as nftables.

Rules may describe properties such as:

- direction
- protocol
- source or destination
- port or port range
- allow or deny behavior

The important architectural separation is:

```text
Control Plane
     │
     │ policy
     ▼
NSG Definition
     │
     │ materialized as
     ▼
Host nftables State
```

The control-plane policy is authoritative, while the physical host enforces it.

Detailed NSG API and rule semantics may be specified independently without changing the fundamental network model.

---

## Placement Changes

Because network identity belongs logically to the Allocation, Kloigos should preserve that identity across Compute Unit replacement when the infrastructure permits it.

For example:

```text
Before

Allocation A
10.20.30.41
     │
     ▼
CU-1
     │
     ▼
Host-A


After

Allocation A
10.20.30.41
     │
     ▼
CU-2
     │
     ▼
Host-B
```

This is possible only when `10.20.30.41` is valid and routable on Host-B's network.

Kloigos must not pretend that an IP is portable when the underlying physical network does not support that portability.

A placement operation may therefore be constrained to hosts compatible with the Allocation's existing network identity.

Alternatively, operations that explicitly permit a network identity change may allocate a new IP.

The exact migration policy belongs to future placement and migration designs.

---

## Failure and Cleanup

Networking participates in the same transactional provisioning principles as CPU, memory, and storage.

Consider:

```text
Reserve CPU
    ↓
Reserve Memory
    ↓
Reserve IP
    ↓
Configure IP
    ↓
Apply nftables rules
    ↓
Storage setup FAILED
```

The provisioning operation must clean up the network resources created for the failed Compute Unit.

Cleanup may include:

- removing nftables rules
- removing host IP configuration
- removing temporary network state
- releasing the IP reservation

The address must not be returned to the available pool while stale host configuration can still use it.

Likewise, failure during cleanup must be visible and recoverable rather than silently treating the address as safe for reuse.

---

## Reconciliation

The control plane records intended network state.

The host contains actual network state.

These may diverge because of:

- failed provisioning
- interrupted cleanup
- administrator changes
- host reboot
- software failure
- partial configuration

Kloigos should therefore be able to reconcile expected and actual network state.

Conceptually:

```text
Control Plane
IP 10.20.30.41 → Allocation A
          │
          │ compare
          ▼
Physical Host
IP configuration
nftables state
Compute Unit association
```

A database assignment alone is not proof that the network boundary is correctly enforced.

---

## IPv4 and IPv6

The architecture does not inherently depend on IPv4.

IP pools may represent IPv4 or IPv6 infrastructure as long as the physical network and host configuration support the corresponding addresses.

Support for specific address families is an implementation capability rather than a change to the core architecture.

The same principles remain:

- administrator-provided addresses
- explicit allocation
- compatibility-aware placement
- host-native configuration
- enforceable workload ownership
- safe release and reuse

---

## No Mandatory Overlay Network

Kloigos deliberately does not require an overlay network as part of its base execution architecture.

This means Kloigos does not depend on mechanisms such as an internal virtual subnet, encapsulated workload network, or mandatory software-defined router merely to provide Compute Unit connectivity.

The base model is:

```text
Workload
    ↓
Compute Unit boundary
    ↓
Linux host networking
    ↓
Physical NIC
    ↓
Physical network
```

Higher-level systems running inside a Compute Unit may introduce their own networking.

For example, Kubernetes running on Kloigos may deploy a CNI plugin and construct a Kubernetes network between its nodes and pods.

That network exists **inside the resources delegated to Kubernetes** and does not replace the Kloigos host-native networking model.

---

## Validation Requirements

Networking guarantees must be tested against real hosts rather than inferred only from control-plane state.

Validation should verify at minimum:

- IP allocation from configured pools
- uniqueness of active IP assignments
- clean exhaustion behavior
- host-side address configuration
- connectivity to the intended Compute Unit
- isolation between Compute Units
- source-address ownership enforcement
- nftables policy enforcement
- NSG enforcement
- cleanup after normal teardown
- cleanup after failed provisioning
- safe IP reuse
- concurrent IP reservations
- behavior after host restart where applicable
- consistency between control-plane and host state

Detailed execution of these tests belongs in the **Validation Architecture** design.

---

## Architectural Invariants

The Kloigos networking model is governed by the following invariants:

1. **Kloigos uses administrator-provided IP infrastructure rather than inventing an overlay address space for Compute Units.**

2. **Each active Allocation receives an explicit network identity from a compatible IP pool.**

3. **An IP address cannot simultaneously belong to multiple active Allocations unless an explicitly designed networking feature requires shared addressing.**

4. **IP reservations must be concurrency-safe.**

5. **IP availability is part of schedulable infrastructure capacity.**

6. **The scheduler must respect network compatibility when selecting physical hosts.**

7. **Logical network identity belongs to the Allocation while host-side network realization belongs to the Compute Unit.**

8. **Kloigos must enforce which Compute Unit is permitted to use an Allocation's network identity.**

9. **Control-plane network state must correspond to real host-side configuration and enforcement.**

10. **Failed provisioning must not leak IP reservations or stale network configuration.**

11. **An IP must not be returned for reuse while stale host configuration could still use that address.**

12. **Placement changes may preserve an Allocation's IP only when the destination infrastructure can legitimately support that address.**

13. **Network Security Group policy is defined by the control plane and enforced on the physical host.**

14. **Higher-level networking introduced by workloads such as Kubernetes does not redefine the Kloigos host-native networking model.**

---

## Related Design Documents

This document defines Kloigos network identity and host-native networking architecture.

Related behavior is defined in:

- **Compute Unit and Allocation Model** — logical ownership versus physical realization of network identity.
- **Dynamic Compute Unit Provisioning** — IP reservation during CU creation and release during teardown.
- **Scheduling and Placement Model** — network capacity and compatibility as placement constraints.
- **Security and Isolation Model** — network isolation as part of the overall security boundary.
- **Tenancy Model** — physical-host sharing and organizational isolation.
- **Nested Orchestration / Kubernetes Model** — networking created by systems operating inside Compute Units.
- **Validation Architecture** — verification of network enforcement and failure behavior.

The central networking principle is:

> **Kloigos gives Allocations real infrastructure network identities and uses the physical host's native Linux networking stack to enforce their use.**
