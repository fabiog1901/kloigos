# Validation profile convention

Profiles are YAML documents stored in this directory. They describe *what* a real-host validation
run requests; they do not contain executable commands, host credentials, or environment-specific
secrets.

## Version 1 fields

```yaml
schema_version: 1
name: smoke
description: Read-only checks of configured host and Compute Unit state.
destructive: false
categories:
  - cgroups
  - networking
diagnostics: on_failure
```

Required fields:

- `schema_version`: positive integer for the profile format.
- `name`: lowercase, hyphen-separated profile identifier, unique in this directory.
- `description`: brief human-readable purpose.
- `destructive`: whether the profile may alter target-host state or generate load.
- `categories`: one or more logical check groups.
- `diagnostics`: one of `never`, `on_failure`, or `always`.

Future profiles may add versioned fields. A runner must reject unknown schema versions and may
reject unknown fields for a version it supports. The initial `smoke.yaml` is declarative only; its
checks are introduced in the smoke-profile phase.
