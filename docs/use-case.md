---
hide:
  - navigation
---

# Product Positioning

Kloigos is a **Linux-native bare-metal Platform as a Service**.

It provides a curated execution platform for Linux applications running on shared physical servers.
Rather than virtualizing hardware or orchestrating containers, Kloigos uses existing Linux primitives
to create isolated, predictable application environments called **Compute Units**.

A Compute Unit is not a virtual machine and does not contain its own operating system. It shares the
host Linux kernel while providing dedicated CPU resources, memory limits, filesystem ownership,
networking, and user identity.

## Why Kloigos Exists

Powerful Linux servers are often underutilized because the usual ways to share them are either too
heavy or too opinionated.

Virtual machines provide strong isolation, but add operational overhead and duplicate operating
systems. Kubernetes and container platforms are powerful, but they assume image-based deployment,
container-native operations, and a larger orchestration model.

Kloigos occupies the space between bare-metal Linux and container orchestration:

> **A Linux-native bare-metal Platform as a Service that provides VM-like application isolation using standard Linux primitives, without virtualization or containers.**

The primary value proposition is operational simplicity. Kloigos lets infrastructure teams safely
partition powerful Linux servers into multiple isolated application environments while preserving
native performance, predictable resource allocation, and a familiar Linux experience.

## Built from Proven Linux Technologies

Kloigos intentionally does not replace Linux. It assembles proven Linux capabilities into a coherent
platform:

- systemd and cgroups for resource management
- nftables for network isolation
- Linux users and filesystem permissions for identity and storage isolation
- LVM for logical storage management
- AppArmor profiles for mandatory access control on supported hosts
- standard Linux networking for floating IP management
- Ansible playbooks for auditable host operations

The value of Kloigos is not a new kernel primitive. Its value is the consistent operational model it
builds from those primitives.

## Compute Units and Allocations

Kloigos separates **capacity** from **identity**.

A **Compute Unit** represents available compute capacity on a host:

- CPU allocation
- memory limits
- NUMA placement
- local storage assignment
- current capacity state

An **Allocation** represents the durable identity of a workload:

- allocation identifier
- Unix login user
- IP address
- storage identity
- metadata and tags
- current Compute Unit placement

This split is central to scaling. When a workload scales up, scales down, or moves to a different
host, the Allocation remains the same. Its login user, IP address, storage identity, tags, and
metadata stay stable. Only the Compute Unit placement changes.

## Curated Runtime Environment

Kloigos does not require applications to be containerized or rewritten.

Applications may be deployed as:

- self-contained binaries
- Java applications with bundled runtimes
- Python virtual environments
- Node.js applications
- standard Linux services managed through `systemd --user`

Kloigos can also support runtime profiles, where hosts provide a curated set of commonly used
runtimes and development tools such as Java, Python, Node.js, Go, Rust, GCC, Clang, CMake, and Git.
This gives application owners a productive execution environment without requiring them to install
system packages.

## Security Philosophy

Kloigos follows an EC2-like operating model: users receive SSH access to their isolated execution
environment and can manage their own processes.

Security is enforced by the platform, not by requiring users to launch applications through a
specific mechanism.

The primary security boundaries are:

- Linux users
- cgroups and systemd slices
- filesystem ownership and quotas
- dedicated IP addresses
- nftables network isolation
- AppArmor profiles on supported hosts
- capability auditing through journald

Systemd service sandboxing directives such as `PrivateTmp`, `ProtectSystem`, and
`SystemCallFilter` can be useful for Kloigos-managed services, but they are not treated as primary
security mechanisms. Users can start processes directly from an interactive shell with tools such as
`nohup`, so Kloigos focuses on platform-level controls that workload authors cannot bypass.

## Where Kloigos Fits

Kloigos is not intended to replace every virtual machine or every Kubernetes cluster.

It is a good fit for:

- infrastructure teams with large bare-metal Linux servers
- internal platforms for trusted but isolated users
- stateful services that expect SSH, writable filesystems, and systemd
- build servers, CI runners, research clusters, and training environments
- performance-sensitive workloads where VM or orchestration overhead is undesirable

It is not the right tool for:

- hostile multi-tenant environments requiring separate kernels
- teams deeply invested in image-based container operations
- workloads that depend on Kubernetes ecosystem features such as sidecars or service meshes
- ephemeral stateless microservice fleets

Kloigos is the missing middle: simpler than Kubernetes, lighter than VMs, more structured than
"just give everyone a Unix account", and built from the Linux tools operators already understand.
