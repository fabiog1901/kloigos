# Kloigos | Κλοηγός

Kloigos is a Linux-native control plane for managing **compute units**: lightweight, VM-like
execution environments carved directly out of a host using standard Linux primitives.

Instead of relying on virtual machines or container orchestration,
Kloigos subdivides large servers into isolated compute units by combining CPU pinning,
resource limits, filesystem isolation, and network controls.

Each compute unit behaves like a small, dedicated machine, with its own Unix user, SSH access,
and systemd-managed services - while sharing the host kernel and avoiding virtualization overhead.

## The problem Kloigos solves

On modern servers with dozens or hundreds of CPUs, teams often need to run multiple independent workloads
on the same machine while maintaining:

- predictable CPU and resource allocation

- strong isolation between workloads

- a familiar, VM-like user experience (SSH, systemd, writable filesystem)

- minimal operational overhead

Traditional solutions - virtual machines, containers, or Kubernetes - can be too heavy, too complex,
or too opinionated for this use case.

Kloigos fills the gap by providing
**fine-grained, host-level isolation without introducing a hypervisor or container runtime**.

## Documentation

This repository contains the source code for Kloigos.

For full documentation, design details, and usage guides, please visit:

👉 <https://fabiog1901.github.io/kloigos/>
