# Instance Classes

## Overview

An **Instance Class** is an administrator-defined, user-facing compute product.

It packages infrastructure choices into a simple abstraction that users can request without needing to understand physical Host models, CPU overcommit, or other infrastructure implementation details.

```text
Host Families ─────┐
                   |
CPU Policy ────────┼──> Instance Class ──> User Request
                   |
Future resource ───┘
characteristics
```

Instance Classes describe **what kind of compute service is being requested**, not a pre-created Compute Unit inventory.

---

## Example

An administrator may define:

```yaml
instance_class:
  name: general-purpose

  eligible_host_families:
    - amd-epyc-gen4
    - intel-xeon-gen5

  cpu_policy:
    shared-standard
```

A user requests:

```yaml
instance_class: general-purpose

resources:
  cpu: 8
  memory: 32GiB
```

The user does not need to select:

- CPU vendor;
- physical Host;
- Logical CPU Manager;
- overcommit ratio;
- physical CPU IDs;
- CPU scheduler configuration.

Those are infrastructure concerns resolved by Kloigos.

---

## Host Families

An Instance Class defines which Host Families may satisfy the request.

For example:

```text
general-purpose
    |
    +-- amd-epyc-gen4
    +-- intel-xeon-gen5
```

This allows multiple physical hardware generations or vendors to provide the same user-facing product where administrators consider them equivalent for that class.

---

## CPU Policy

An Instance Class references a CPU Policy.

For example:

```text
general-purpose
    -> shared-standard

economical
    -> shared-economy

compute-optimized
    -> dedicated
```

Users therefore select an Instance Class rather than directly selecting an overcommit ratio or CPU scheduling policy.

---

## Resource Size

Instance Class and resource size are separate concepts.

For example:

```text
Instance Class:
general-purpose

CPU:
8

Memory:
32 GiB
```

An Instance Class may permit flexible sizing or administrator-defined standard sizes.

Dynamic Compute Unit provisioning means these sizes do not require pre-created Compute Unit shapes.

---

## Avoiding the Cartesian Product

Kloigos should not automatically expose every possible combination of:

```text
Host Family
×
CPU Policy
×
resource size
```

as a user-visible product.

Administrators deliberately define the Instance Classes they want to expose.

This keeps infrastructure complexity under administrator control.

---

## Tenancy

Tenancy is conceptually independent from Instance Class.

For example:

```text
Instance Class:
general-purpose

Tenancy:
dedicated
```

Administrators may choose to expose separate Instance Classes for commercial or operational reasons, but the architecture should not require tenancy to be encoded into the Instance Class.

---

## Relationship to the Allocator

The Instance Class provides placement constraints to the Allocator.

```text
User Request
      |
      v
Instance Class
      |
      +-- Eligible Host Families
      +-- CPU Policy
      |
      v
Allocator
```

The Allocator resolves these constraints against current infrastructure capacity.

---

## Pricing

Instance Classes provide a natural user-facing unit for pricing and chargeback.

Pricing may eventually depend on:

- Instance Class;
- CPU quantity;
- memory;
- storage;
- GPU resources;
- tenancy;
- allocation duration.

Pricing remains administrator-defined and is separate from placement semantics.

---

## Design Invariants

> Instance Classes are administrator-defined user-facing compute products.

> Host Families describe hardware; Instance Classes describe products.

> CPU Policies describe CPU delivery behavior; Instance Classes select a CPU Policy.

> Users normally do not select raw CPU overcommit ratios.

> An Instance Class may support multiple Host Families.

> A Host Family may participate in multiple Instance Classes.

> Instance Classes do not represent pre-created Compute Unit inventory.

> Instance Class and resource size are separate concepts.

> Kloigos does not automatically expose the Cartesian product of all infrastructure options.

> The Allocator resolves Instance Classes into infrastructure placement constraints.
