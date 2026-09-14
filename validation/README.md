# Kloigos real-host validation

This directory defines the real-host validation harness for Kloigos. Unlike unit or integration
tests of the Python codebase, this harness will exercise and inspect Linux hosts and Compute Units
managed by Kloigos.

It is intended to answer operational questions such as whether a deployed allocation has the
expected cgroup, networking, storage, and isolation boundaries. It is not a general-purpose test
framework and it must only run against hosts explicitly selected for validation.

## Current scope

This foundation establishes the directory layout, declarative profile convention, stable report
contract, idempotent Ansible preparation for explicitly selected validation hosts, and a local
runner MVP. It intentionally includes no host-check adapters or workload generation.

- `profiles/` contains declarative validation profiles.
- `report.schema.json` defines the versioned machine-readable result format.
- `examples/` contains a valid illustrative report.
- `reports/` and `artifacts/` are local, ignored destinations for generated output.
- `ansible/` contains validation-host preparation.
- `runner/` contains the Kloigos-specific reporting runner.

## Safety model

Profiles must state whether they are destructive. A future runner must require explicit user
selection before it runs a destructive profile, and must write all reports and collected evidence
under this directory. Profiles must not embed shell commands or credentials; executable behavior
belongs to the runner and its documented adapters.

## Report contract

Every completed run will write one JSON report conforming to `report.schema.json` and a concise
human-readable summary. The JSON report is the authoritative automation interface:

- `schema_version` allows compatible evolution of the contract.
- `run` identifies the requested profile, target, and timing.
- `summary` provides stable aggregate counts and final status.
- `results` records one result per check with a stable check identifier.
- `diagnostics`, when present, points to collected evidence rather than embedding secrets or
  arbitrarily large output.

The terminal summary includes the profile, target, final status, pass/fail/skip/error counts, and
paths to the JSON report and artifacts. The runner's documented exit-status contract is available
in `runner/README.md`.

## Phased ownership

- Smoke, enforcement, workload, contention, diagnostics, and CI profiles are implemented in their
  respective later phases.
