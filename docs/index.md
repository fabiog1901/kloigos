---
hide:
  - navigation
  - toc
---

# VM-like isolation. Bare-metal performance. No orchestration.

## Kloigos lets you split a powerful server into multiple independent compute environments - without virtual machines or containers

---

Kloigos is a Linux-native control plane for managing **compute units**: lightweight, VM-like
execution environments carved directly out of a host using standard Linux primitives.

Instead of relying on virtual machines or container orchestration,
Kloigos subdivides large servers into isolated compute units by combining CPU pinning,
resource limits, filesystem isolation, and network controls.

Each compute unit behaves like a small, dedicated machine, with its own Unix user, SSH access,
and systemd-managed services - while sharing the host kernel and avoiding virtualization overhead.

It gives teams a simple, VM-like way to run multiple workloads on the same host, with predictable performance, strong isolation, and a familiar Linux experience. No orchestration layers, no images, no extra overhead - just efficient use of the hardware you already have.

---

### Benefits

**Kloigos makes it easy to divide a single machine into multiple isolated compute units**, each with its own resources, user space, and lifecycle. It offers the convenience of virtual machines without the complexity or cost of virtualization.

Kloigos allows you to run multiple independent workloads on the same host with predictable performance and minimal overhead. By building directly on Linux primitives, it delivers VM-like isolation while staying fast, simple, and transparent.

Each compute unit behaves like a lightweight VM - with SSH access, systemd services, and isolated resources - while avoiding the complexity of containers and hypervisors. It’s a pragmatic way to share powerful servers without surprises.
