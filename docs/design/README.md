# Kloigos Design Documents

This directory contains the durable architectural design documentation for Kloigos.

Design documents preserve **why Kloigos works the way it does**, the major architectural decisions behind each subsystem, and the invariants future implementations must preserve.

## Documentation Model

Kloigos uses three complementary forms of documentation:

| Documentation | Purpose |
|---|---|
| **Product Context Snapshots** | What is Kloigos? A concise view of the product and its overall architecture. |
| **Design Documents** | Why does Kloigos work this way? Durable architectural decisions, boundaries, tradeoffs, and invariants. |
| **GitHub Issues** | What needs to be implemented or changed? Concrete development work and acceptance criteria. |

Design documents should focus on architecture rather than source-code implementation details. They remain relevant after the corresponding GitHub issues have been closed.

Not every feature requires a design document. A design document is appropriate when a subsystem contains architectural decisions that future contributors need to understand and preserve.

## Design Documents

| Design document | Purpose |
|---|---|
| **Architecture Overview** | Describes the major Kloigos architectural concepts and how the core subsystems fit together. |
| **Compute Unit and Allocation Model** | Defines the distinction between Compute Units as execution capacity/placement and Allocations as durable workload identities. |
| **Host Families** | Defines how administrators classify Hosts by infrastructure characteristics independently of resource-delivery policy. |
| **Instance Classes** | Defines the user-facing compute products that combine eligible Host Families, CPU Policy, and resource characteristics. |
| **CPU Policy Model** | Defines reusable Dedicated and Shared CPU delivery policies and their capacity semantics. |
| **Logical CPU Manager** | Defines the Host-local resource manager that owns physical CPUs, implements a CPU Policy, and exposes allocatable capacity. |
| **Shared and Burstable CPU** | Defines proportional CPU entitlement, overcommit, bursting, contention behavior, and enforcement boundaries for Shared CPU. |
| **Dynamic Compute Unit Allocator** | Defines how Kloigos selects and reserves the infrastructure resources required by an Allocation. |
| **Dynamic Compute Unit Provisioner** | Defines how Kloigos materializes a Compute Unit from resource assignments recorded in an Allocation. |
| **CPU Resource Model** | Defines Dedicated and Shared CPU, CPU pools, cpusets, scheduling controls, bursting, overcommit, NUMA, and CPU isolation semantics. |
| **Scheduling and Placement Model** | Defines how Instance Classes, Host Families, host capacity, topology, tenancy, networking, and other constraints determine placement. |
| **Networking and IP Model** | Defines host-native networking, administrator-managed IP pools, IP allocation, nftables enforcement, and network lifecycle. |
| **Security and Isolation Model** | Defines Kloigos security boundaries and the roles of Linux users, cgroups, filesystem permissions, nftables, AppArmor, SSH, and the shared kernel. |
| **Storage and Persistence Model** | Defines storage allocation, LVM, persistent Allocation storage, Compute Unit lifecycle, teardown, and migration semantics. |
| **Tenancy Model** | Defines shared and dedicated physical-host tenancy and the scheduling and isolation invariants associated with them. |
| **Metering and Pricing Model** | Defines allocation-based metering, administrator-defined pricing, price history, resource changes, and chargeback/showback semantics. |
| **Nested Orchestration / Kubernetes Model** | Defines how systems such as K3s operate inside Compute Units, including cgroup delegation and outer/inner resource boundaries. |
| **Validation Architecture** | Defines how Kloigos validates its architectural guarantees on real hosts, including orchestration, enforcement testing, contention testing, and diagnostics. |

These documents should be added as their architecture becomes sufficiently understood. The presence of an entry here does not imply that its design is finalized or implemented.

## Using These Documents

For significant Kloigos work, contributors and Codex should use context in this order:

```text
Product Context Snapshot
        ↓
Relevant Design Documents
        ↓
GitHub Issue
        ↓
Current Source Code
```

If implementation work changes an architectural decision or reveals that an existing design is incomplete, the relevant design document should be updated deliberately.

## Guiding Principle

This directory exists to preserve architectural reasoning that would otherwise disappear into conversations, source code, or closed GitHub issues.

A future contributor should be able to understand not only **how Kloigos is built**, but **why its important architectural boundaries exist**.
