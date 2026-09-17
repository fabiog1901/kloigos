# Kloigos real-host validation

The validation process manually verifies Kloigos behavior on explicitly selected test hosts. It
preserves the real execution path - local controller, Ansible, and Kloigos host - without production
discovery or automatic triggers. `make validate` is the only normal manual entry point.

```bash
make validate
```

## Components and flow

1. [`report.py`](report.py) is the local controller and report evaluator. It reads the selected fixture manifest,
   validates the required controller inputs, assigns a run ID, and starts the one remote Ansible
   playbook.
2. [`fixtures/example.yaml`](fixtures/example.yaml) is the single declarative fixture-manifest
   template. It names disposable resources used for real-host validation; it is the only
   environment-specific validation configuration. The controller can create and remove only the
   allocations and IP addresses declared in that manifest.
3. [`ansible/RUN_VALIDATION.yaml`](ansible/RUN_VALIDATION.yaml) creates a per-run workspace on
   each explicitly inventoried host, performs Linux inspection or workload commands, and writes
   per-subsection YAML evidence records immediately under `evidence/` in that workspace. Each
   filename is `<group>.<subsection>.yaml` and each record ID is
   `<group>.<subsection>.<behavior>`. IDs describe the behavior being verified rather than the
   implementation tool, so they remain stable if a workload tool changes. The matching Ansible
   check task is named `<group> | <subsection> | <behavior>` and registers its result as
   `<group>__<subsection>__<behavior>`; a YAML comment immediately before the task preserves its
   human-friendly description.
4. Ansible archives the complete workspace as a `.tar.gz` bundle and fetches it to the selected
   report directory (default: `validation/reports/controller`). The bundle is the immutable audit
   artifact for that host and run.
5. The local `report.py` reads each fetched bundle, aggregates its ordered per-subsection records into
   adjacent `*.evidence.yaml`, evaluates them, and writes the human-readable YAML report (for
   example, `k01-<run-id>.report.yaml`). It determines the final validation exit status; no
   reporting code is copied to the remote host.

Each remote evidence file is written as soon as its check subsection completes. This prevents an
`all` run from replacing earlier results, keeps individual evidence documents bounded, and preserves
completed diagnostics in the archived workspace if a later check fails. The controller owns the
aggregate evidence document, so it is derived only from the fetched immutable bundle.

`ansible/PREPARE_VALIDATION_HOST.yaml` is an administrator preparation aid. It is not part of a
normal validation run.

## Check groups

`--group` defaults to `all`, which runs every check group: `smoke`, `resources`, `network`, and
`workloads`. Set it to one of those individual groups to run only that bounded subset.
`resources` uses the allocation selected from the fixture manifest to inspect cgroup limits,
verify CPU-affinity, memory, and PID-limit enforcement, and verify the declared Compute Unit LVM
mount, allocation mount, ownership, and optional declared peer filesystem boundary. The memory and
PID probes run in short-lived child scopes beneath the allocation slice, with deliberately small
`MemoryMax` and `TasksMax` values; they verify kernel cgroup enforcement without attempting to
consume the allocation's full configured limit. `workloads` runs bounded
`stress-ng` CPU, memory, process, and disk work as that allocation user and creates a temporary,
integrity-verified file on the declared allocation mount. Because `all` includes workloads, the
default run requires explicit consent. The fio command is capped at 30 seconds and both the
filesystem-access probe and fio file are removed on command exit:

```bash
make validate ARGS="--allow-destructive --fixture-manifest /path/to/fixtures.yaml --fixture-allocation validation-a"
```

## CLI inputs and fixtures

Use `make validate ARGS="--help"` to see the CLI options. The inventory must contain only
explicitly designated test hosts. The normal all-groups run needs `--inventory`,
`--fixture-manifest`, `--fixture-allocation`, and `--allow-destructive`; `--report-dir` selects
where fetched bundles and YAML reports are retained. Command-line values override their matching
`KLOIGOS_VALIDATION_*` environment variables, which remain available as fallbacks.

For storage validation, the selected allocation must declare `storage_mount_path` and
`allocation_mount_path`. Set `filesystem_peer_allocation_id` to another allocation declared in the
same manifest to enable the peer-access-denial test; without it, that one test is reported as
skipped. Paths are explicit fixture inputs—the runner does not discover or probe other allocation
mounts.

For network validation, the selected allocation must declare `ip_address`,
`network_spoof_ip_address`, `network_probe_ipv4`, `network_probe_ipv6`, and
`network_probe_port`. The probe destinations must be explicitly designated test endpoints running
an iperf3 server. The alternate source address must belong to the fixture environment (normally a
second allocation on the same host). The runner makes only bounded connections to those declared
destinations and does not change host networking.

Security Group connection validation additionally uses the manifest's `security_groups` and
`network_connection_probes` lists. A probe endpoint is either a `validation_host` named under
`servers` or an `allocation` named under `allocations`; allocation endpoints may reside on the same
server or on a different declared server. Every probe names its direction, protocol, destination
port, expected result, and (for an allowed connection) the fixture rule that permits it. The runner
starts a bounded disposable listener for both allowed and denied probes, so denial is not confused
with a closed destination port. Probe and fixture-rule IDs become stable report and diagnostic
identities; generated Kloigos Security Group and rule IDs are recorded alongside them.

For the local demo, provision and later remove those declared resources explicitly:

```bash
make validate ARGS="fixtures setup --fixture-manifest /path/to/fixtures.yaml"
make validate ARGS="--inventory validation/inventory.ini --fixture-manifest /path/to/fixtures.yaml --fixture-allocation validation-a --allow-destructive"
make validate ARGS="fixtures cleanup --fixture-manifest /path/to/fixtures.yaml"
```

The fixture commands poll every queued allocation or deallocation job to completion and never
discover or alter resources outside the manifest.
