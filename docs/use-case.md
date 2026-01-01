---
hide:
  - navigation
---

# Use Case

Kloigos is a Linux-native control plane for managing **compute units**: lightweight, VM-like
execution environments carved directly out of a host using standard Linux primitives.

## The problem Kloigos solves

On modern servers with dozens or hundreds of CPUs, teams often need to run multiple independent workloads
on the same machine while maintaining:

- predictable CPU and resource allocation

- strong isolation between workloads

- a familiar, VM-like user experience (SSH, systemd, writable filesystem)

- minimal operational overhead

Traditional solutions - virtual machines, containers, or Kubernetes - can be too heavy, too complex,
or too opinionated for this use case. Kloigos fills the gap by providing
**fine-grained, host-level isolation without introducing a hypervisor or container runtime**.

## Use case for Kloigos

Kloigos can be broadly useful - but only for a specific class of users and environments.
It’s not a universal replacement for VMs, containers, or Kubernetes, and that’s actually a strength, not a weakness.

Let’s frame this clearly.

## 1. What problem Kloigos _really_ solves

At its core, Kloigos solves this problem:

> “How do I safely and efficiently subdivide a large Linux server into multiple _VM-like_ environments **without** a hypervisor or container stack, while keeping a familiar SSH + systemd user experience?”

That problem exists **far more often than people realize**, especially outside hyperscale cloud-native teams.

Kloigos is most compelling where people want:

- **strong isolation**
- **very low overhead**
- **standard Linux tooling**
- **no Kubernetes**
- **no hypervisor**
- **no image pipelines**

---

## 2. Who would find Kloigos immediately useful

### 1) Infrastructure / platform teams with large bare-metal servers

Common in:

- finance / trading
- telco
- research labs
- enterprise data centers
- on-prem AI / ML clusters

These teams often have:

- 64-256 core machines
- predictable workloads
- strong isolation requirements
- skepticism toward Kubernetes overhead

Kloigos lets them:

- slice machines deterministically
- assign ownership cleanly
- avoid VM sprawl
- keep performance predictable

---

### 2) Teams running “pet services” rather than cattle

Not every workload fits the container model.

Examples:

- stateful services
- legacy daemons
- services that expect a writable filesystem
- software that assumes SSH access
- systemd-managed services
- licensed software bound to host identity

Kloigos gives them:

- isolation without rewriting deployment models
- an EC2-like mental model
- predictable CPU and IO placement

---

### 3) Multi-tenant environments with _trusted but isolated_ users

Examples:

- internal developer platforms
- shared build servers
- CI runners
- academic compute clusters
- training environments

These environments need:

- real isolation
- fair resource usage
- simple cleanup
- minimal ops burden

Kloigos fits perfectly here.

---

### 4) Performance-sensitive workloads

Kloigos avoids:

- VM exits
- container overlay filesystems
- network overlays
- extra scheduler layers

This matters for:

- low-latency services
- HPC-style workloads
- NUMA-sensitive applications
- IO-heavy pipelines

---

## 3. Where Kloigos is _not_ a good fit

Kloigos is _not_ ideal for:

- untrusted internet-facing tenants (shared kernel risk)
- workloads needing strong kernel isolation guarantees
- ephemeral, stateless, image-based microservices
- teams deeply invested in Kubernetes
- workloads that rely on container ecosystems (sidecars, service mesh, etc.)

Those users should stick with:

- Kubernetes
- microVMs (Firecracker)
- traditional VMs

---

## 4. How wide is the adaptability?

### Conceptually

Kloigos is adaptable to **any environment that already runs Linux and systemd**.

It does not require:

- special kernels
- special hardware
- custom runtimes
- vendor lock-in

That makes it _portable_ and _incrementally adoptable_.

---

### Practically

Kloigos is best described as:

> **“A Linux-native, VM-like abstraction layer for subdividing large machines.”**

That’s a niche - but it’s a **real and recurring niche**, and it’s underserved by existing tools.

---

## 5. Why this niche exists (and persists)

Many teams are stuck between:

- **VMs** → too heavy, too expensive
- **Containers** → too opinionated, too complex, too ephemeral

Kloigos occupies the missing middle ground:

- stronger isolation than “just users”
- simpler than Kubernetes
- lighter than VMs
- more flexible than containers

This “middle ground” is surprisingly common in real-world ops.

---

## 6. The strongest argument for Kloigos

The strongest argument isn’t technical—it’s experiential:

> “Give a developer SSH access, systemd, predictable resources, and no surprises.”

That’s an incredibly powerful value proposition.

Many engineers **want**:

- a small VM
- with guaranteed CPU and IO
- without having to understand Kubernetes internals

Kloigos delivers exactly that.

---

## 7. Final honest assessment

Kloigos is not for everyone - and that’s okay.

It is:

- ❌ not a general-purpose cloud platform
- ❌ not a Kubernetes replacement
- ❌ not a security boundary for hostile tenants

But it _is_:

- ✅ a compelling alternative for a real, underserved segment
- ✅ technically sound
- ✅ operationally elegant
- ✅ easy to reason about
- ✅ easy to adopt incrementally

We present Kloigos clearly as:

> **“VM-like compute units without VMs, built from native Linux primitives”**
