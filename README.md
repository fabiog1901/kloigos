# Kloigos | Κλοηγός

Kloigos is a **Linux-native bare-metal Platform as a Service** for running applications on shared
physical servers.

Instead of virtualizing hardware or orchestrating containers, Kloigos uses standard Linux primitives
to provide isolated, predictable application environments called **Compute Units**. A Compute Unit is
not a virtual machine and does not contain its own operating system. It shares the host Linux kernel
while providing dedicated CPU resources, memory limits, filesystem ownership, networking, and user
identity.

## The problem Kloigos solves

On modern servers with dozens or hundreds of CPUs, teams often need to run multiple independent workloads
on the same machine while maintaining:

- predictable CPU and resource allocation

- strong isolation between workloads

- a familiar, VM-like user experience (SSH, systemd, writable filesystem)

- minimal operational overhead

Traditional solutions - virtual machines, containers, or Kubernetes - can be too heavy, too complex,
or too opinionated for this use case.

Kloigos fills the gap as:

> **A Linux-native bare-metal Platform as a Service that provides VM-like application isolation using standard Linux primitives, without virtualization or containers.**

The value of Kloigos is not that it replaces Linux technologies. It integrates systemd, cgroups,
nftables, Linux users, LVM, standard networking, and mandatory access-control mechanisms into a
consistent operational model for deploying, managing, and scaling applications.

## Compute Units and Allocations

Kloigos separates capacity from workload identity.

A **Compute Unit** represents available host capacity: CPU allocation, memory limits, NUMA placement,
and local storage.

An **Allocation** represents a workload identity and owns the allocation identifier, Unix login user,
IP address, storage, tags, metadata, and current Compute Unit placement.

When a workload scales or moves, only its Compute Unit placement changes. Its user, IP address,
storage identity, and metadata remain stable.

## Security Model

Kloigos follows an EC2-like model: users receive SSH access to their isolated execution environment
and can manage their own processes. Security is enforced by the platform rather than by requiring
users to start applications through a specific launcher.

The primary boundaries are Linux users, cgroups and systemd slices, filesystem ownership, dedicated
IP addresses, nftables isolation, and mandatory access-control profiles such as AppArmor. Systemd
service sandboxing can be useful for managed services, but it is not treated as the primary security
boundary because users may start processes directly from an interactive shell.

## Install

Kloigos is published on PyPI, but while the project is moving quickly the recommended
install path is the latest committed GitHub `main` branch:

```bash
pip install "kloigos @ git+https://github.com/fabiog1901/kloigos.git@main"
```

The built-in demo mode starts an embedded Postgres database:

```bash
kloigos demo
```

For a production-style setup, export `KLOIGOS_DB_URL` and `KLOIGOS_MASTER_KEY`, for example, via a `.env` file,
then run:

```bash
kloigos init
kloigos serve
```

## Documentation

This repository contains the source code for Kloigos.

For full documentation, design details, and usage guides, please visit:

👉 <https://fabiog1901.github.io/kloigos/>

## Licensing

Kloigos is released under the **Apache License 2.0**. All features are open source.
See the `LICENSE` file for the full license text.
