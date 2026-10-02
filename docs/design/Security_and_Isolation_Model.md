# Security and Isolation Model

## Purpose

Kloigos provides isolated Linux execution environments directly on shared physical hosts without introducing a hypervisor or requiring workloads to run inside containers.

Isolation is created by composing standard Linux security and resource-control mechanisms.

The core principle is:

> **A Compute Unit is a Linux-enforced security and resource boundary, not a separate operating system boundary.**

Kloigos is designed to provide strong operational isolation between workloads while retaining the performance, simplicity, and familiarity of native Linux execution.

Because Compute Units share the physical host's Linux kernel, Kloigos does not claim the same security boundary as hardware virtualization.

This document defines the security model, trust boundaries, defense layers, administrative responsibilities, and security invariants of Kloigos.

Detailed CPU, networking, storage, tenancy, and provisioning behavior belongs in their respective design documents.

---

## Security Model

At a high level:

```text
Physical Host
┌─────────────────────────────────────────────┐
│                Linux Kernel                 │
│                                             │
│   ┌─────────────┐      ┌─────────────┐      │
│   │ Compute     │      │ Compute     │      │
│   │ Unit A      │      │ Unit B      │      │
│   │             │      │             │      │
│   │ Workload A  │      │ Workload B  │      │
│   └─────────────┘      └─────────────┘      │
│                                             │
│  Linux users       cgroups                  │
│  filesystem ACLs   nftables                 │
│  AppArmor          systemd                  │
│  auditing          resource controls        │
│                                             │
└─────────────────────────────────────────────┘
```

Compute Units share the host kernel but receive independent identities, resources, filesystem access, networking identities, and security policies.

No single Linux mechanism provides the entire isolation boundary.

Kloigos deliberately combines several mechanisms so that each controls a different aspect of workload behavior.

---

## Trust Boundary

The physical Linux host and Kloigos administrative components are trusted infrastructure.

Users operating inside Compute Units are not granted administrative control over the physical host.

The principal isolation boundary is:

```text
Infrastructure Administrator
        │
        │ controls
        ▼
Physical Host / Kloigos
        │
        │ establishes boundaries
        ▼
Compute Unit
        │
        │ user controls workload
        ▼
Application Processes
```

Users may receive significant freedom inside their Compute Unit, including SSH access and the ability to execute arbitrary application processes.

That freedom must remain bounded by the resources and permissions assigned to the Compute Unit.

---

## Shared Kernel

All Compute Units on a physical host share its Linux kernel.

This is a deliberate architectural property.

Kloigos therefore differs from a virtual-machine architecture:

```text
Virtual Machines

VM-A              VM-B
 │                  │
Kernel A          Kernel B
 │                  │
└──── Hypervisor ───┘


Kloigos

CU-A              CU-B
 │                  │
 └──── Linux Kernel ┘
          │
     Physical Host
```

This provides several advantages:

- no guest operating systems
- no hypervisor layer
- native Linux execution
- reduced infrastructure duplication
- direct use of host hardware
- centralized operating-system administration

It also establishes an important security boundary:

> **A kernel compromise can potentially cross Compute Unit boundaries.**

Kloigos must not describe Compute Units as having the same isolation properties as independent virtual machines.

---

## Defense in Depth

Kloigos isolation is composed from multiple Linux controls.

Conceptually:

```text
                 Compute Unit
                      │
        ┌─────────────┼─────────────┐
        │             │             │
     Identity      Resources      Network
        │             │             │
   Linux users      cgroups       nftables
   permissions      cpusets       IP ownership
        │             │             │
        └───────┬─────┴─────┬───────┘
                │           │
            Filesystem   AppArmor
                │           │
                └─────┬─────┘
                      │
                 Linux Kernel
```

The failure or misconfiguration of one layer should not unnecessarily eliminate all other boundaries.

---

## User Identity

Each Allocation receives an appropriate Linux identity used to execute its workload.

Unix users and groups provide a fundamental isolation mechanism for:

- process ownership
- filesystem ownership
- permissions
- signals
- local IPC access
- execution identity

Workloads must not execute as unrestricted host root.

Administrative operations required to construct or manage Compute Units are performed by trusted Kloigos infrastructure rather than delegated directly to workload users.

The exact identity lifecycle belongs to the Compute Unit and Allocation implementation.

---

## SSH Access

SSH is a primary access mechanism for Kloigos Compute Units.

Users should be able to interact with their environment as a normal Linux system:

```text
User
 │
 │ SSH
 ▼
Allocation IP
 │
 ▼
Compute Unit
 │
 ▼
User Linux Session
```

SSH access does not imply host administrative access.

Authentication credentials, authorized keys, Unix identity, filesystem permissions, resource controls, and security policy must ensure that the session remains inside the boundaries associated with the Allocation.

SSH Key Pair management may be exposed as a control-plane feature while the public key is materialized into the Allocation's execution environment.

---

## Resource Isolation

Resource isolation is part of the security model because one workload must not be able to consume resources promised to another.

Kloigos uses cgroups and related Linux controls to enforce boundaries such as:

- CPU
- memory
- process/task count
- potentially I/O and other resource controllers

Dedicated CPU additionally requires exclusive CPU placement.

Resource exhaustion by one Compute Unit should remain constrained by the policies assigned to that Compute Unit.

Detailed semantics belong in the corresponding resource design documents.

---

## Filesystem Isolation

Unix filesystem ownership and permissions provide the foundation for filesystem isolation.

A workload must not be able to access another Allocation's files merely because both execute on the same physical host.

Persistent storage belonging to an Allocation must retain appropriate ownership and access controls when attached to a Compute Unit.

Host administrative files and Kloigos infrastructure state must remain inaccessible to ordinary workload users.

Additional controls such as AppArmor may further restrict filesystem access where appropriate.

Detailed persistence and attachment behavior belongs in the **Storage and Persistence Model** design.

---

## Network Isolation

Each Allocation receives an explicit network identity.

Kloigos uses native Linux networking and nftables to ensure that a Compute Unit can use the network identity assigned to it but cannot freely impersonate another Allocation.

For example:

```text
CU-A
10.20.30.41
     │
     │ permitted
     ▼
Physical Network


CU-B
10.20.30.42
     │
     ├── 10.20.30.42 permitted
     │
     └── 10.20.30.41 denied
```

Network Security Groups may further restrict inbound and outbound communication.

Network policy is defined by the control plane and enforced by the physical host.

Detailed behavior belongs in the **Networking and IP Model** design.

---

## AppArmor

AppArmor provides an additional policy layer beyond ordinary Unix permissions.

Kloigos may use AppArmor profiles to restrict actions available to processes associated with Compute Units.

Potential controls include access to:

- sensitive host paths
- kernel interfaces
- privileged system resources
- device files
- administrative interfaces

AppArmor is part of a defense-in-depth strategy rather than the sole Compute Unit isolation mechanism.

Profiles should be designed so that Kloigos can provide useful Linux environments without granting unnecessary access to the underlying host.

---

## systemd

systemd is used as an important resource-management and lifecycle mechanism.

It may provide:

- cgroup hierarchy management
- process grouping
- resource-control configuration
- workload lifecycle integration
- delegation where appropriate

systemd also provides service sandboxing capabilities.

However:

> **systemd service sandboxing is supplementary protection, not the primary Kloigos security boundary.**

A user with SSH access can execute processes directly from a shell rather than exclusively through a predefined systemd service.

Kloigos security guarantees therefore cannot depend solely on sandbox directives attached to individual services.

---

## Privileged Operations

Compute Unit users must not receive unrestricted capabilities that would allow them to reconfigure host-level isolation.

Examples include the ability to:

- modify host nftables policy
- change other Compute Units' cgroups
- reassign CPU sets
- configure arbitrary host IP addresses
- access another Allocation's storage
- modify AppArmor policy
- administer the physical host
- bypass resource controls

Operations requiring such privileges belong to trusted Kloigos infrastructure.

Where controlled delegation is required, it must be explicit and limited to the intended resource subtree.

---

## Nested Orchestration

Systems such as Kubernetes may require controlled delegation of Linux capabilities, particularly cgroup management.

For example:

```text
Kloigos
 │
 ▼
Compute Unit boundary
 │
 └── delegated cgroup subtree
          │
          ▼
         K3s
          │
          ├── Pod A
          ├── Pod B
          └── Pod C
```

The nested system may subdivide resources assigned to the Compute Unit.

It must not be able to expand beyond the outer Kloigos boundary.

The principle is:

> **Delegation permits subdivision of assigned resources, not escalation beyond them.**

Detailed behavior belongs in the **Nested Orchestration / Kubernetes Model** design.

---

## Tenancy

Multiple organizations may share a physical Kloigos host when shared tenancy is permitted.

This means workloads from different organizations may share the same Linux kernel.

Organizations requiring a stronger infrastructure boundary may request Dedicated Server Tenancy.

Conceptually:

```text
Shared Host

Organization A CU
Organization B CU
Organization C CU

       shared kernel


Dedicated Host

Organization A CU
Organization A CU
Organization A CU

       shared kernel

No other organization
may use this host
```

Dedicated Server Tenancy reduces cross-organization kernel-sharing exposure but does not create separate kernels between Compute Units belonging to the same organization.

Detailed scheduling and lifecycle semantics belong in the **Tenancy Model** design.

---

## Administrative Boundary

Infrastructure administrators have privileged access to the physical hosts.

Kloigos does not attempt to protect workloads from a malicious administrator with unrestricted host root access.

An administrator controlling the host kernel can inherently bypass Linux process, filesystem, cgroup, and networking boundaries.

Therefore the infrastructure administrator is part of the trusted computing base.

Operational controls around administrative access, credentials, auditing, and host management remain important but are distinct from Compute Unit isolation.

---

## Host Security

Because Compute Units share the host kernel, host security directly affects every workload on that host.

Kloigos therefore depends on sound host operational practices such as:

- timely kernel security updates
- controlled administrative access
- minimal unnecessary host services
- secure SSH configuration
- appropriate AppArmor policy
- auditing and logging
- controlled package installation
- secure Kloigos service credentials

The host operating system is infrastructure owned by the administrator, not by individual application users.

This centralizes responsibility for maintaining the underlying Linux environment.

---

## Auditing and Observability

Security boundaries must be observable.

Kloigos should retain enough information to determine:

- which Allocation ran on which Compute Unit
- which physical host provided that CU
- which Unix identity represented the workload
- which resources were assigned
- which IP address was assigned
- which security policies were applied
- when placement or configuration changed

Host mechanisms such as journald, system logs, kernel messages, nftables state, cgroup state, and AppArmor events may provide evidence when diagnosing security or isolation failures.

The exact audit retention model may evolve independently.

---

## Failure and Cleanup

Security boundaries must remain correct during provisioning failures and teardown.

For example:

```text
Create Unix identity
        ↓
Create cgroup
        ↓
Configure storage
        ↓
Configure network
        ↓
Apply nftables
        ↓
Apply AppArmor
        ↓
Provisioning FAILED
```

Cleanup must remove temporary security state without exposing another workload to stale permissions or resource ownership.

Particular care is required before reusing:

- Unix identities
- IP addresses
- storage
- CPU assignments
- filesystem paths
- security-policy associations

A resource must not be treated as safely reusable while stale state could allow the previous Allocation to access or influence it.

---

## Reconciliation

The control plane records intended security policy.

The physical host enforces actual policy.

These states may diverge.

For example:

```text
Control Plane

CU-A
 ├── CPUs 4-7
 ├── IP 10.20.30.41
 └── Security Policy A
           │
           │ compare
           ▼
Physical Host

cgroups
cpusets
filesystem permissions
IP configuration
nftables
AppArmor
process ownership
```

Kloigos should be capable of detecting important divergence between intended and actual enforcement.

A database record alone does not prove that a security boundary exists.

---

## Validation Requirements

Security and isolation guarantees must be tested against real physical hosts.

Validation should verify both correct configuration and attempts to violate the boundary.

Examples include:

### Identity and Process Isolation

- correct workload Unix identity
- inability to signal unauthorized processes
- inability to modify another CU's resource controls
- process/task limits

### CPU and Memory

- CPU boundary enforcement
- Dedicated CPU exclusivity
- Shared CPU pool boundaries
- memory limit enforcement
- behavior under contention

### Filesystem

- inability to read or modify another Allocation's files
- inability to access protected host paths
- correct persistent-storage ownership

### Networking

- correct IP ownership
- inability to impersonate another Allocation's IP
- Network Security Group enforcement
- cleanup and safe address reuse

### Security Policy

- AppArmor profile application
- prohibited operations actually denied
- delegated operations remain within their assigned boundary

### Tenancy

- Dedicated hosts reject placement from other organizations
- shared hosts enforce Compute Unit boundaries

Validation must include attempts to escape or exceed configured limits.

Inspecting configuration alone is insufficient.

Detailed validation execution belongs in the **Validation Architecture** design.

---

## Security Non-Goals

Kloigos should state clearly what the architecture does not attempt to provide.

The base security model does not provide:

- separate kernels for every Compute Unit
- hardware-virtualization isolation between Compute Units
- protection from a malicious physical-host administrator with root access
- protection from vulnerabilities that fully compromise the shared host kernel
- unrestricted root-equivalent privileges for workload users
- hostile public-cloud multi-tenancy equivalent to strongly isolated virtual machines

These are architectural boundaries, not implementation defects.

Workloads requiring a different isolation model may require virtual machines, physically dedicated infrastructure, or another execution environment.

---

## Architectural Invariants

The Kloigos security model is governed by the following invariants:

1. **Compute Units share the physical host's Linux kernel.**

2. **Kloigos must not represent Compute Unit isolation as equivalent to hardware virtualization.**

3. **Workload users must not receive unrestricted physical-host administrative privileges.**

4. **Compute Unit isolation is built from multiple Linux mechanisms rather than relying on a single control.**

5. **Resource guarantees recorded by the control plane must correspond to real host-side enforcement.**

6. **A workload must not be able to modify another Compute Unit's resource boundaries.**

7. **A workload must not be able to access another Allocation's persistent data merely because both share a host.**

8. **A Compute Unit must not be able to use another Allocation's network identity without explicit policy permitting it.**

9. **Dedicated resources must retain the exclusivity promised by their resource model.**

10. **systemd service sandboxing is supplementary and must not be treated as the sole workload security boundary.**

11. **Nested delegation may subdivide assigned resources but must not allow expansion beyond the outer Compute Unit boundary.**

12. **Dedicated Server Tenancy must prevent other organizations from being scheduled onto a host while that dedicated tenancy is active.**

13. **The physical-host administrator is part of the trusted computing base.**

14. **Failed provisioning and teardown must not leave stale security state that compromises subsequent workloads.**

15. **Security guarantees must be validated through actual enforcement and violation attempts, not merely configuration inspection.**

---

## Related Design Documents

This document defines the overall Kloigos security and isolation boundary.

Related behavior is defined in:

- **Compute Unit and Allocation Model** — distinction between durable workload identity and the execution boundary.
- **CPU Resource Model** — Dedicated and Shared CPU isolation.
- **Networking and IP Model** — network identity, nftables enforcement, and Network Security Groups.
- **Storage and Persistence Model** — filesystem ownership and persistent-data isolation.
- **Tenancy Model** — shared and dedicated physical-host tenancy.
- **Dynamic Compute Unit Provisioning** — safe creation, rollback, teardown, and resource reuse.
- **Nested Orchestration / Kubernetes Model** — controlled resource delegation.
- **Validation Architecture** — enforcement, escape, and contention testing.

The central security principle is:

> **Kloigos provides Linux-native isolation through layered kernel-enforced controls while explicitly recognizing that Compute Units share the physical host's kernel and therefore do not constitute a virtual-machine security boundary.**
