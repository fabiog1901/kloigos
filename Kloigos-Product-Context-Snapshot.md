# Kloigos Product Context Snapshot

**Generated:** 2026-09-14\
**Audience:** Codex, maintainers, documentation authors, product and
architecture contributors\
**Purpose:** Canonical product-level context for interpreting,
implementing, and documenting Kloigos.

> **Important:** This snapshot describes the intended/current Kloigos
> product as a coherent whole. Features described here should be treated
> as existing product capabilities for purposes of product positioning
> and documentation, even if some implementation work is still being
> completed in the repository. Do not weaken or omit the product model
> merely because an individual implementation task is unfinished.

------------------------------------------------------------------------

## 1. Executive Definition

Kloigos is a **Linux-native bare-metal compute platform** that turns a
heterogeneous fleet of physical Linux servers into a programmable
internal compute cloud.

It provides cloud-like infrastructure primitives while using standard
Linux mechanisms rather than virtual machines or containers as its
fundamental infrastructure abstraction.

Kloigos allows organizations to request isolated compute capacity from a
shared fleet while the platform manages:

- compute resources
- durable workload identity
- networking and IP allocation
- storage
- security policy
- SSH access
- tenancy
- heterogeneous hardware placement
- instance classes
- scheduling
- metering and pricing
- lifecycle management
- validation and enforcement

A concise definition is:

> **Kloigos turns a heterogeneous bare-metal Linux fleet into a
> programmable internal compute cloud using standard Linux primitives.**

Kloigos is broader than an application PaaS. Documentation that defines
Kloigos primarily as a PaaS or application platform should be updated to
reflect this infrastructure-platform model.

------------------------------------------------------------------------

## 2. Product Philosophy

Kloigos is based on a simple idea:

> Modern Linux already contains many of the primitives needed to safely
> partition and manage powerful physical servers.

Instead of introducing a hypervisor, guest operating systems, or
mandatory containerization, Kloigos composes existing Linux capabilities
into a controlled infrastructure platform.

Core Linux technologies include:

- systemd
- cgroups v2
- Linux users and groups
- filesystem ownership and permissions
- LVM
- standard Linux networking
- nftables
- AppArmor where supported
- journald and Linux audit facilities
- standard SSH/OpenSSH
- Ansible for deterministic host operations

The architectural preference is:

> **Use standard Linux primitives where they provide the required
> capability instead of creating unnecessary proprietary abstractions.**

The control plane owns desired state.

The physical Linux hosts enforce that state.

------------------------------------------------------------------------

## 3. What Kloigos Is Not

Kloigos is not:

- a hypervisor
- a virtual-machine platform
- a system-container platform
- a container orchestrator
- a Kubernetes replacement
- a Kubernetes distribution
- an overlay-network platform
- a mandatory application packaging system
- a general-purpose secret manager
- a payment processor
- a general accounting platform

Applications running on Kloigos do not need to be containerized.

A Compute Unit does not contain its own operating system or kernel.

Compute Units on the same physical server share the host Linux kernel.

Therefore, Kloigos does not claim VM-grade isolation between Compute
Units.

For security domains requiring kernel-level separation between mutually
hostile tenants, virtual machines or separate physical hosts may remain
more appropriate.

Kloigos addresses this risk operationally through controls including
**Dedicated Tenancy**, where an entire physical host is reserved for a
single organization.

------------------------------------------------------------------------

## 4. Product Positioning

Kloigos occupies a useful middle layer between unmanaged bare-metal
Linux, virtualization, and container orchestration.

### Compared with virtual machines

Kloigos avoids:

- guest operating systems
- hypervisor overhead
- VM image management
- duplicated operating-system maintenance
- unnecessary virtualization for trusted internal workloads

It provides native Linux execution and substantially lighter operational
overhead.

The tradeoff is that Compute Units on a shared host use the same kernel.

### Compared with Kubernetes

Kloigos does not require:

- containers
- container images
- Kubernetes manifests
- Kubernetes networking
- Kubernetes operators
- Kubernetes as the infrastructure control plane

Users can receive an Allocation, connect over SSH, and run ordinary
Linux software.

Kubernetes can itself run **inside Kloigos Compute Units**, allowing
Kloigos to act as the bare-metal resource layer underneath Kubernetes
when container orchestration is useful.

### Compared with Unix accounts on servers

Kloigos provides much more than user-account isolation.

It adds controlled infrastructure primitives including:

- deterministic CPU allocation
- memory limits
- process/task limits
- storage
- dedicated IP addresses
- security groups
- SSH key management
- shared and dedicated tenancy
- hardware-aware scheduling
- Instance Classes
- lifecycle management
- organization ownership
- allocation-based metering
- administrator-defined pricing
- auditable infrastructure state

A useful positioning statement is:

> **Kloigos provides the missing middle: lighter than VMs, simpler than
> Kubernetes, and far more structured than simply creating Unix accounts
> on Linux servers.**

------------------------------------------------------------------------

## 5. Core Object Model

Several Kloigos concepts must remain distinct.

``` text
Physical Host
    ↓
Host Family
    ↓
Instance Class eligibility
    ↓
Compute Unit
    ↓
Allocation
```

They represent different concerns.

### Physical Host

An actual Linux server managed by Kloigos.

### Host Family

An administrator-facing classification describing similar physical
hardware.

### Instance Class

A stable user-facing hardware/product class such as:

- general-purpose
- compute-optimized
- memory-optimized
- storage-optimized
- gpu
- economical

### Compute Unit

A defined quantity of compute capacity on a physical host.

### Allocation

The durable workload identity consuming a Compute Unit.

The distinction between Compute Unit and Allocation is especially
important.

------------------------------------------------------------------------

## 6. Compute Units

A **Compute Unit (CU)** represents compute capacity carved from a
physical Linux host.

A CU may define:

- CPU allocation
- CPU affinity/cpuset
- memory limits
- NUMA placement
- task/PID limits
- local storage assignment
- disk controls
- network identity/enforcement
- other resource constraints

Conceptually:

``` text
Physical Linux Host
│
├── Compute Unit A
│   ├── CPU allocation
│   ├── memory boundary
│   ├── storage
│   └── networking
│
├── Compute Unit B
│
└── Compute Unit C
```

A Compute Unit is **not a virtual machine**.

It has:

- no guest OS
- no independent kernel
- no virtual hardware requirement

It uses the host Linux kernel and standard Linux resource controls.

------------------------------------------------------------------------

## 7. Allocations

Kloigos intentionally separates **capacity from identity**.

### Compute Unit

Represents the available/assigned compute capacity.

### Allocation

Represents the durable workload identity.

An Allocation includes or references concepts such as:

- Allocation ID
- owning organization
- Unix login identity
- assigned IP address
- storage identity
- SSH keys
- security groups
- Instance Class
- tenancy mode
- metadata/tags
- current Compute Unit placement
- metering history

The architectural rule is:

> **Compute Unit = capacity and placement. Allocation = durable workload
> identity.**

For example:

``` text
Allocation A
     │
     ├── CU-17 / Host A
     │
     └── later
          CU-42 / Host B
```

The workload remains Allocation A even if its placement changes.

Features representing workload identity should normally follow the
Allocation.

------------------------------------------------------------------------

## 8. Resource Management

Kloigos primarily uses **systemd and cgroups v2** to enforce Compute
Unit resource boundaries.

Relevant controls include:

- CPU
- CPU affinity/cpuset
- memory
- PIDs/tasks
- storage and I/O controls where supported
- nested cgroup delegation where explicitly enabled

Linux users and filesystem permissions provide identity and filesystem
isolation.

AppArmor provides additional host-enforced policy where available.

Kloigos does not consider configuration alone sufficient evidence that
isolation works.

The system's validation philosophy is:

> **Validate configured state, then deliberately attempt to violate
> it.**

------------------------------------------------------------------------

## 9. Networking Model

Every Allocation receives its own IP address.

Kloigos networking does not depend on Docker-style overlays, container
bridge networks, or VM virtual networking merely to provide workload
addresses.

Instead, addresses are configured using normal Linux networking on the
physical host.

Conceptually:

``` text
Physical Host NIC
    │
    ├── Host IP
    ├── Allocation A IP
    ├── Allocation B IP
    └── Allocation C IP
```

These are real addresses from administrator-provided network space.

Kloigos uses **nftables** and standard Linux networking primitives to
associate and enforce the use of an address by the intended Compute
Unit/Allocation.

The platform prevents one Allocation from arbitrarily using or
impersonating another Allocation's address.

This networking model is intentionally Linux-native rather than
overlay-based.

------------------------------------------------------------------------

## 10. IP Address Pools

IP addresses are a first-class infrastructure resource.

Kloigos administrators configure one or more pools of addresses that
Kloigos is permitted to allocate.

Kloigos does not invent its own overlay address space.

Conceptually:

``` text
Administrator
     ↓
IP Pools
     ↓
Kloigos IP Allocation
     ↓
Allocation
     ↓
Physical Host NIC
     ↓
nftables enforcement
```

Pools may represent distinctions such as:

- subnet
- VLAN
- datacenter
- environment
- network class
- routability

Kloigos tracks:

- available addresses
- reserved addresses
- allocated addresses
- released addresses
- ownership/history

IP availability participates in provisioning and scheduling.

If CPU, memory, storage, and host capacity are available but no suitable
IP address exists, the Allocation cannot be provisioned.

Duplicate IP assignment must never occur.

The IP is primarily associated with the **Allocation identity**, not
merely the temporary Compute Unit placement.

Where the physical network topology permits it, the address follows the
Allocation when it moves.

------------------------------------------------------------------------

## 11. Network Security Groups

Kloigos provides **Network Security Groups** similar conceptually to AWS
EC2 security groups.

Security Groups are control-plane policies describing which network
traffic is permitted for an Allocation.

Example:

``` yaml
security_group:
  name: database

  ingress:
    - protocol: tcp
      port: 5432
      source:
        security_group: application

    - protocol: tcp
      port: 22
      source:
        cidr: 10.20.0.0/16
```

Security Groups may define:

- allowed protocols
- allowed ports
- source CIDRs
- destination rules
- references to other Security Groups

The model is:

> **Control-plane policy, host-enforced.**

Kloigos compiles the desired policy into host-level **nftables**
enforcement.

The workload does not need to cooperate with the policy and must not be
able to weaken another Allocation's rules.

Security Group identity follows the Allocation even when its physical
placement changes.

------------------------------------------------------------------------

## 12. SSH Key Pair Management

SSH keys are first-class Kloigos resources.

Users can:

- import an existing SSH public key
- ask Kloigos to generate a new key pair
- select one or more keys when provisioning an Allocation
- add keys to an existing Allocation
- remove or revoke keys
- rotate access credentials

The fundamental security rule is:

> **Kloigos stores public keys. Kloigos does not persist private keys.**

For imported keys, the private key never enters Kloigos.

For generated key pairs:

``` text
Kloigos generates key pair
        ↓
Stores public key
        ↓
Returns private key exactly once
        ↓
Does not retain recoverable private key
```

If the private key is lost, it cannot be downloaded again.

Users create/import another key.

Multiple SSH keys can be associated with one Allocation so teams do not
need to share private keys.

Example:

``` yaml
allocation:
  ssh_keys:
    - alice-laptop
    - bob-workstation
    - ci-automation
```

Kloigos installs the selected public keys into the Allocation Unix
user's:

``` text
~/.ssh/authorized_keys
```

with correct OpenSSH ownership and permissions.

SSH access follows the **Allocation identity** rather than physical
placement.

------------------------------------------------------------------------

## 13. Shared and Dedicated Tenancy

Kloigos supports both **Shared Tenancy** and **Dedicated Tenancy**.

### Shared Tenancy

Compute Units belonging to multiple organizations may coexist on the
same physical Linux host.

Example:

``` text
Shared Host
├── CU-001 → Organization A
├── CU-002 → Organization A
├── CU-003 → Organization B
└── CU-004 → Organization C
```

### Dedicated Tenancy

A physical host assigned to dedicated tenancy for Organization A may
contain only Compute Units/Allocations belonging to Organization A.

Invariant:

``` text
If host.tenancy_mode == dedicated:
    every Allocation on the host
    MUST belong to host.dedicated_organization_id
```

Example:

``` text
Dedicated Host → Organization A
├── CU-001 → Organization A
├── CU-002 → Organization A
└── CU-003 → Organization A
```

Placement of an Organization B Allocation on that host must be rejected.

Dedicated Tenancy reduces cross-organization shared-kernel exposure by
ensuring the physical host is exclusive to one organization.

It does not create separate kernels between Compute Units belonging to
that organization.

### Dedicated Host Lifecycle

A host must not immediately transition from one organization's dedicated
use to another organization's use without sanitization.

Conceptually:

``` text
DEDICATED(A)
     ↓
DRAINING
     ↓
SANITIZING
     ↓
AVAILABLE
     ↓
DEDICATED(B)
```

Sanitization may include cleanup of:

- Unix users
- SSH configuration
- credentials
- storage/LVM state
- files/directories
- IP/network state
- nftables state
- cgroups/systemd state
- AppArmor state
- temporary data
- tenant-specific artifacts

A reboot may be part of the sanitization policy where required.

------------------------------------------------------------------------

## 14. Heterogeneous Hardware

Kloigos is designed to operate across heterogeneous physical-server
fleets.

An enterprise may have dozens of different hardware families, including
combinations of:

- AMD CPUs
- Intel CPUs
- different CPU generations
- high-frequency CPU systems
- high-core-count systems
- memory-dense systems
- NVMe/storage-dense systems
- GPU systems
- AI accelerator systems
- older economical hardware
- different server manufacturers and models

This physical complexity should not leak directly into the normal user
provisioning API.

------------------------------------------------------------------------

## 15. Host Families

A **Host Family** is an administrator-facing description of a group of
sufficiently similar physical systems.

Examples:

``` text
dell-r7625-epyc-9654
hpe-dl380-xeon-8592
gpu-h100-8x
nvme-storage-gen2
legacy-intel-gen4
```

Host records also contain factual hardware capabilities such as:

``` yaml
host:
  cpu:
    vendor: AMD
    model: EPYC
    cores: 192

  memory:
    total_gib: 1536

  storage:
    type: nvme
    capacity_tib: 15

  accelerators:
    - vendor: nvidia
      model: H100
      count: 8
```

Host Families and physical capability metadata describe **what
infrastructure actually exists**.

They are not the primary workload-facing product abstraction.

------------------------------------------------------------------------

## 16. Instance Classes

Users normally request one of a small number of stable **Instance
Classes**.

Examples:

``` text
general-purpose
compute-optimized
memory-optimized
storage-optimized
gpu
economical
```

An enterprise may expose only five or six Instance Classes while
operating 20, 30, 40, or more Host Families.

Administrators map Host Families to Instance Classes.

Conceptually:

``` text
                         USER API

              ┌──────────────────────────┐
              │     Instance Classes     │
              │                          │
              │  general-purpose         │
              │  compute-optimized       │
              │  memory-optimized        │
              │  storage-optimized       │
              │  gpu                     │
              │  economical              │
              └────────────┬─────────────┘
                           │
                  Administrator Mapping
                           │
              ┌────────────▼─────────────┐
              │       Host Families      │
              │                          │
              │ AMD families             │
              │ Intel families           │
              │ NVMe systems             │
              │ GPU systems              │
              │ legacy systems           │
              │ ...                      │
              └────────────┬─────────────┘
                           │
                    Physical Hosts
```

The principle is:

> **Users request workload characteristics. Administrators decide which
> physical hardware satisfies those characteristics.**

Instance Classes remain stable while underlying hardware evolves.

------------------------------------------------------------------------

## 17. Compute Size and Instance Class Are Separate

Instance Class answers:

> **What kind of hardware?**

Compute Unit size answers:

> **How much capacity?**

Example:

``` yaml
allocation:
  instance_class: compute-optimized

  cpu: 16
  memory: 64GiB
```

Other dimensions compose independently:

``` yaml
allocation:
  instance_class: storage-optimized

  cpu: 16
  memory: 128GiB

  tenancy: dedicated

  storage:
    size: 2TiB

  security_groups:
    - database

  ssh_keys:
    - operations
```

Conceptually:

``` text
Instance Class
    → What kind of hardware?

Compute size
    → How much capacity?

Tenancy
    → Who may share the physical host?

Security Groups
    → Who may communicate with it?

SSH Keys
    → Who may authenticate?

Allocation
    → What is the durable workload identity?
```

------------------------------------------------------------------------

## 18. Scheduling and Placement

The scheduler combines all relevant constraints.

Conceptually:

``` text
Allocation Request
        │
        ├── Instance Class
        ├── CPU
        ├── Memory
        ├── Storage
        ├── Accelerator requirements
        ├── Tenancy
        ├── Network/IP requirements
        └── Additional constraints
                  │
                  ▼
        Eligible Host Families
                  │
                  ▼
        Eligible Physical Hosts
                  │
                  ▼
        Capacity / NUMA / Tenancy /
        Network / IP evaluation
                  │
                  ▼
              Placement
```

Placement must satisfy all hard constraints atomically.

The scheduler must not create invalid intermediate states, particularly
around Dedicated Tenancy and scarce resources such as IP addresses or
GPUs.

------------------------------------------------------------------------

## 19. Storage

Kloigos uses Linux-native storage mechanisms, including LVM, to provide
storage to Allocations.

Storage management should preserve:

- Allocation ownership
- filesystem isolation
- appropriate permissions
- logical volume identity
- capacity limits
- lifecycle correctness

Storage identity should be treated separately from transient physical
Compute Unit placement where the architecture permits it.

Validation must distinguish:

- storage correctness/isolation
- storage performance

Tools such as `fio` can be used for throughput, IOPS, and latency
testing.

------------------------------------------------------------------------

## 20. Curated Runtime Environment

Kloigos workloads do not need to be containerized.

Users can run normal Linux software such as:

- self-contained binaries
- Java applications
- Python virtual environments
- Node.js applications
- Go binaries
- Rust binaries
- `systemd --user` services
- traditional long-running daemons where permitted

Hosts may provide administrator-managed runtime profiles such as:

``` text
minimal
standard
build
```

Possible shared tools include:

- Java
- Python
- Node.js
- Go
- Rust
- GCC
- Clang
- CMake
- Git
- pipx
- uv

The host operating system remains managed centrally rather than
duplicated per Allocation.

------------------------------------------------------------------------

## 21. Security Model

Kloigos follows an EC2-like operational model in which users can receive
SSH access to their isolated Linux execution environment and manage
their own processes.

Security therefore cannot depend solely on a particular process-launch
mechanism.

Platform-level controls include:

- Unix user identity
- cgroups/systemd resource boundaries
- filesystem ownership and permissions
- storage isolation
- dedicated workload IP addresses
- nftables
- Network Security Groups
- AppArmor where supported
- capability/audit information
- Dedicated Tenancy

Systemd service sandboxing may provide additional defense for managed
services, but it is not the primary security boundary because users can
run arbitrary permitted shell processes.

The platform must clearly communicate that Shared Tenancy uses a common
Linux kernel.

------------------------------------------------------------------------

## 22. Allocation-Based Metering

Kloigos provides allocation-based infrastructure metering.

The fundamental billing rule is:

> **Charge for allocated capacity, not observed utilization.**

If an organization reserves:

``` text
16 CPUs
64 GiB RAM
for 10 hours
```

then those allocated resources are the basis for metering regardless of
whether average CPU utilization was:

``` text
5%
```

or:

``` text
100%
```

The reason is that Kloigos reserved that capacity and removed it from
the available pool.

Metering follows the **Allocation**, not the transient physical Compute
Unit placement.

Migration must not restart, lose, or duplicate metering.

------------------------------------------------------------------------

## 23. Administrator-Defined Pricing

Kloigos administrators define prices.

Kloigos does not impose a commercial pricing model.

Pricing may depend on dimensions including:

- Instance Class
- CPU allocation
- memory allocation
- storage
- storage class
- GPUs/accelerators
- accelerator model/count
- Dedicated Tenancy
- other future features

Conceptually:

``` yaml
pricing:
  instance_class: gpu

  cpu:
    per_core_hour: 0.08

  memory:
    per_gib_hour: 0.01

  accelerator:
    nvidia-h100:
      per_device_hour: 3.50

  storage:
    nvme:
      per_gib_month: 0.10

  tenancy:
    dedicated:
      multiplier: 1.25
```

These values are administrator policy.

------------------------------------------------------------------------

## 24. Price Estimation Before Provisioning

Before creating an Allocation, users can see its expected/current cost.

For example:

``` text
Instance Class: compute-optimized
CPU:            16
Memory:         64 GiB
Storage:        500 GiB
Tenancy:        shared

Estimated Price
────────────────────────
Hourly:          $X.XX
Daily:           $XX.XX
Monthly:         $XXX.XX
```

The estimate uses the same pricing engine as actual metering.

This allows users to understand the economic consequence of a
provisioning decision before committing resources.

------------------------------------------------------------------------

## 25. Dynamic and Versioned Pricing

Prices can change while an Allocation continues running.

Pricing schedules are therefore effective-dated and versioned.

Example:

``` text
January
Price Schedule v1
$5.00

February
Price Schedule v2
$4.50

March
Price Schedule v3
$5.50
```

A three-month Allocation spanning all three schedules is rated using the
appropriate price during each interval.

Conceptually:

``` text
Allocation
────────────────────────────────────────>

Jan 1            Feb 1             Mar 1
  │                │                 │

Price v1         Price v2          Price v3
$5.00            $4.50             $5.50

└── Segment 1 ──┘└── Segment 2 ──┘└── Segment 3 ──┘
```

Changes that affect cost create new metering segments, including:

- pricing changes
- Allocation resize
- Instance Class changes
- tenancy changes
- other billable-resource changes

Historical pricing schedules are immutable once used.

Historical costs must remain reproducible.

------------------------------------------------------------------------

## 26. Kloigos Is Not the Payment System

Kloigos calculates infrastructure consumption and cost.

It does **not** perform the financial settlement.

The boundary is:

``` text
Kloigos
    ↓
Allocation Metering
    ↓
Pricing / Rating
    ↓
Auditable Cost Records
    ↓
External System
    ↓
Accounting / Chargeback / Invoice / Payment
```

Kloigos does not need to implement:

- payment processing
- credit cards
- bank transfers
- invoicing
- tax collection
- accounts receivable
- financial settlement

It provides authoritative records that external FinOps, accounting,
billing, or cost-center systems can consume.

This supports both:

- **showback** --- informing an organization what its consumption cost
- **chargeback** --- providing records used by another system to
    financially allocate that cost

------------------------------------------------------------------------

## 27. Auditable Cost Records

Kloigos must be able to answer:

``` text
Who owned this Allocation?

When was it active?

Which resources were allocated?

Which Instance Class applied?

Which tenancy mode applied?

Which pricing schedules applied?

When did resource or price changes occur?

How was each segment calculated?

What was the resulting total?
```

Historical records must remain meaningful even after:

- the Allocation is deleted
- its Compute Units disappear
- physical servers are retired
- Host Family mappings change
- Instance Classes evolve
- current prices change

------------------------------------------------------------------------

## 28. Kubernetes / K3s on Kloigos

Kloigos can run Kubernetes as a workload rather than making Kubernetes
the infrastructure layer.

The preferred initial Kubernetes distribution is **K3s**.

Example:

``` text
Physical Server
│
├── CU1 → K3s control plane
├── CU2 → K3s worker
├── CU3 → K3s worker
└── CU4 → native stateful workload
```

This demonstrates that one physical server can simultaneously support:

- containerized/stateless workloads through Kubernetes
- native/stateful/performance-sensitive Linux workloads directly
    through Kloigos

The cgroup hierarchy should preserve Kloigos as the outer authority:

``` text
Host
└── Kloigos
    ├── CU2: 4 CPU / 16 GiB
    │   └── K3s
    │       ├── Pod A
    │       ├── Pod B
    │       └── Pod C
    │
    └── CU4: 12 CPU / 64 GiB
        └── Native database
```

The invariant is:

> **A nested orchestrator may subdivide resources Kloigos gives it, but
> it must never administer resources outside its Compute Unit.**

Systemd/cgroup delegation (`Delegate=yes`) and cgroup v2 are central to
this model.

K3s networking/runtime requirements must not weaken normal Kloigos
isolation.

------------------------------------------------------------------------

## 29. Validation Harness

Kloigos includes a deterministic validation system for proving that
resource and security boundaries actually hold on real Linux servers.

Ansible is used for orchestration, but assertions belong in the Kloigos
validation logic rather than being improvised by Ansible or Codex.

The architectural principle is:

> **Ansible orchestrates. The validation runner decides PASS or FAIL.**

The harness validates areas including:

- cgroups
- CPU
- memory
- PIDs/tasks
- storage
- disk I/O
- networking
- IP ownership
- Security Groups
- SSH access
- filesystem/Unix identity
- AppArmor
- Shared/Dedicated Tenancy
- Host Family/Instance Class placement
- pricing/metering
- contention
- nested K3s resource boundaries

------------------------------------------------------------------------

## 30. Validation Philosophy

The fundamental test pattern is:

``` text
Configuration Test
        +
Enforcement / Escape Test
        +
Contention Test
```

Or:

> **Validate the configured state, then deliberately attempt to violate
> it.**

Examples:

### Memory

Do not only inspect `memory.max`.

Attempt to exceed the limit and prove the kernel constrains the
workload.

### CPU

Do not only inspect cpuset configuration.

Saturate CPUs and prove the process executes only on allowed CPUs.

Attempt to escape the allowed CPU set.

### PIDs

Approach/exceed `pids.max` and verify additional forks fail without
harming sibling Allocations.

### Networking

Do not only inspect nftables.

Attempt both permitted and prohibited connections.

Attempt IP impersonation.

### Security Groups

Verify permitted traffic succeeds and prohibited traffic actually fails.

### AppArmor

Verify the profile exists, then attempt prohibited behavior and confirm
denial/audit evidence.

### Dedicated Tenancy

Attempt incompatible cross-organization placement and ensure it is
rejected atomically.

### Pricing

Run otherwise identical Allocations at different actual CPU utilization
and prove their cost remains identical when allocated capacity and
duration are identical.

------------------------------------------------------------------------

## 31. Contention Testing

Kloigos must prove that boundaries continue to hold when multiple
workloads stress different resources simultaneously.

Example:

``` text
CU-A → CPU saturation
CU-B → memory pressure
CU-C → disk I/O saturation
CU-D → network load + near pids.max
```

The validation harness verifies:

- each CU remains within its limits
- sibling workloads remain isolated
- the host remains healthy
- policy enforcement remains intact

This is critical because resource isolation that works only under idle
conditions is insufficient.

------------------------------------------------------------------------

## 32. Deterministic Remote Testing

Kloigos development requires testing on real remote Linux servers.

The preferred workflow is:

``` text
Developer request
        ↓
Codex modifies Kloigos
        ↓
Ansible deploys to test hosts
        ↓
Validation Harness executes
        ↓
Structured PASS / FAIL
        ↓
Codex diagnoses failures
        ↓
Modify and rerun
```

Codex should not invent success criteria during execution.

The repository and validation harness encode deterministic assertions.

This is particularly important because many Kloigos behaviors cannot be
meaningfully validated through ordinary CI alone.

------------------------------------------------------------------------

## 33. Product-Level Resource Composition

A Kloigos Allocation can be thought of as a composition of independent
infrastructure dimensions.

``` text
Organization
     │
     ▼
Allocation
     │
     ├── Instance Class
     │      What kind of hardware?
     │
     ├── Compute Size
     │      How much CPU/memory?
     │
     ├── Storage
     │      How much/what storage?
     │
     ├── Tenancy
     │      Who may share the physical host?
     │
     ├── IP Address
     │      What network identity?
     │
     ├── Security Groups
     │      Who may communicate with it?
     │
     ├── SSH Keys
     │      Who may authenticate?
     │
     └── Pricing/Metering
            What does the reserved capacity cost?
```

These are composable primitives rather than one monolithic "server
type."

------------------------------------------------------------------------

## 34. Example Provisioning Model

Conceptually, a complete request might resemble:

``` yaml
allocation:
  organization: payments-team

  instance_class: compute-optimized

  resources:
    cpu: 16
    memory: 64GiB

  storage:
    size: 500GiB

  tenancy: dedicated

  network:
    ip_pool: production

  security_groups:
    - backend
    - operations-ssh

  ssh_keys:
    - alice-laptop
    - operations
```

Before provisioning, Kloigos can calculate the current estimated cost.

The scheduler then resolves:

- eligible Host Families
- physical hosts
- resource capacity
- tenancy compatibility
- NUMA constraints
- storage availability
- IP availability
- other hard constraints

and creates the Allocation on a valid Compute Unit.

------------------------------------------------------------------------

## 35. Product Narrative

The strongest product narrative is not:

> "Kloigos is another application platform."

Nor is it:

> "Kloigos replaces Kubernetes."

Instead:

> **Kloigos turns Linux bare metal into consumable cloud-like
> infrastructure without requiring virtualization or making Kubernetes
> the infrastructure layer.**

An infrastructure organization can take:

``` text
Old economical servers
High-core AMD servers
High-frequency Intel servers
Memory-dense servers
NVMe storage systems
GPU/AI systems
Different vendors and generations
```

and expose them through:

``` text
A small stable catalog of Instance Classes
        +
Compute Unit sizing
        +
Dedicated or Shared Tenancy
        +
IP allocation
        +
Security Groups
        +
SSH access
        +
Storage
        +
Metering and pricing
```

This produces a coherent internal compute service over heterogeneous
Linux infrastructure.

------------------------------------------------------------------------

## 36. Important Architectural Invariants

The following invariants should be preserved across implementation and
documentation.

### Allocation Identity

> Allocation identity is durable and distinct from transient Compute
> Unit placement.

### Linux-Native Execution

> A Compute Unit is not a VM and does not have its own kernel or guest
> OS.

### Shared Kernel

> Compute Units on a shared physical host use the host Linux kernel.

### Dedicated Tenancy

> A dedicated host may contain Allocations from exactly one
> organization.

### Hardware Abstraction

> Users normally request Instance Classes; administrators manage Host
> Families and physical hardware mappings.

### Networking

> Allocation addresses come from administrator-provided IP pools and use
> standard Linux networking rather than a Kloigos overlay network.

### Network Enforcement

> Security policy is defined by the control plane and enforced by the
> host, primarily through nftables.

### SSH Keys

> Kloigos persists public keys, not recoverable private keys.

### Metering

> Kloigos meters allocated capacity, not actual workload utilization.

### Pricing

> Administrators define prices; Kloigos applies them deterministically.

### Historical Pricing

> Price changes are prospective and must not rewrite historical cost.

### Financial Boundary

> Kloigos calculates auditable infrastructure cost; external systems
> handle financial settlement.

### Nested Orchestration

> A nested orchestrator may subdivide resources inside its CU but may
> never administer resources outside it.

### Validation

> Configuration must be accompanied by enforcement/escape testing and
> contention testing.

------------------------------------------------------------------------

## 37. Documentation Guidance

Documentation should consistently reflect the product model described in
this snapshot.

In particular:

1. Do not describe Kloigos primarily as a PaaS if that implies its
    scope is limited to application deployment.
2. Do not imply Compute Units are VMs or containers.
3. Do not imply Kloigos uses an overlay network for normal Allocation
    networking.
4. Do not describe physical Host Families as the normal user-facing
    provisioning abstraction.
5. Do not conflate Compute Units with Allocations.
6. Do not describe actual CPU utilization as the basis of Kloigos
    metering.
7. Do not imply Kloigos processes payments.
8. Do not imply Kubernetes is required to use Kloigos.
9. Do not imply Dedicated Tenancy creates separate kernels.
10. Do not imply generated SSH private keys remain recoverable from
    Kloigos.

Documentation should explain the product in terms of composable
cloud-like infrastructure primitives implemented using Linux-native
mechanisms.

------------------------------------------------------------------------

## 38. Guidance to Codex

When working on the Kloigos repository, treat this snapshot as product
and architecture context.

### Preserve the conceptual model

Do not introduce implementation shortcuts that unintentionally collapse
distinctions such as:

``` text
Allocation vs Compute Unit
Instance Class vs Host Family
allocated capacity vs actual utilization
public SSH key vs private key
Kloigos metering vs external payment
shared tenancy vs dedicated tenancy
```

### Prefer deterministic implementation

Where possible:

- encode policy explicitly
- encode validation criteria in the repository
- use Ansible for deterministic remote orchestration
- use Linux primitives directly
- produce machine-readable PASS/FAIL results
- avoid relying on an AI agent to decide whether infrastructure
    behavior is correct

### Flag contradictions

If repository documentation or implementation contradicts this snapshot,
do not silently reinterpret the product.

Identify the contradiction explicitly.

Determine whether:

- the documentation is obsolete
- implementation is incomplete
- implementation reflects an intentional newer design
- this snapshot needs revision

### Treat described product capabilities as part of Kloigos

For product positioning and documentation work, assume the capabilities
in this snapshot exist as part of Kloigos even if a particular feature
branch, issue, or implementation is still in progress.

Implementation status is separate from product-definition status.

------------------------------------------------------------------------

## 39. Concise Product Description

When a short description is needed:

> **Kloigos is a Linux-native bare-metal compute platform that turns
> heterogeneous physical Linux infrastructure into a programmable
> internal compute cloud using standard Linux primitives.**

A slightly longer version:

> **Kloigos lets infrastructure teams expose heterogeneous bare-metal
> Linux servers as a consistent catalog of isolated Compute Units. It
> provides cloud-like capabilities including resource allocation,
> durable workload identity, dedicated IPs, Security Groups, SSH key
> management, Shared and Dedicated Tenancy, hardware-aware Instance
> Classes, storage, and allocation-based metering---without requiring
> virtual machines or making containers and Kubernetes the fundamental
> infrastructure abstraction.**

------------------------------------------------------------------------

## 40. Strategic Direction

Kloigos should continue evolving toward a consistent internal compute
API over heterogeneous enterprise Linux infrastructure.

The long-term value is not merely the ability to partition one large
server.

It is the ability to take an entire physical fleet:

``` text
20–40+ hardware families
Hundreds or thousands of Linux servers
Multiple datacenters and networks
Different performance/cost characteristics
```

and expose it as:

``` text
A small understandable compute catalog
        ↓
Predictable Allocations
        ↓
Linux-native isolation
        ↓
Cloud-like networking/security/access
        ↓
Auditable resource consumption and cost
```

The resulting platform provides many of the infrastructure-management
benefits associated with public-cloud compute while retaining direct
Linux execution and bare-metal operational simplicity.

------------------------------------------------------------------------

## End of Snapshot

This document represents the current coherent product context for
Kloigos as of **2026-09-14**.

Detailed implementation specifications should remain in the repository
and associated design documents. This snapshot exists to keep product
positioning, architecture, terminology, and implementation reasoning
aligned across ChatGPT, Codex, maintainers, and documentation work.
