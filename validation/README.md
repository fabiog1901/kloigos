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
   the raw `evidence.json` file.
4. Ansible archives the complete workspace as a `.tar.gz` bundle and fetches it to
   `KLOIGOS_VALIDATION_REPORT_DIR` (default: `validation/reports/controller`). The bundle is the
   immutable audit artifact for that host and run.
5. The local `report.py` reads each fetched bundle, evaluates its evidence, and writes its adjacent
   human-readable YAML report (for example, `k01-<run-id>.report.yaml`). It determines the final
   validation exit status; no reporting code is copied to the remote host.

`ansible/PREPARE_VALIDATION_HOST.yaml` is an administrator preparation aid. It is not part of a
normal validation run.

## Check groups

Set `KLOIGOS_VALIDATION_GROUP` to one of the stable groups: `smoke` (default), `resources`,
`network`, or `workloads`. `resources` uses the allocation selected from the fixture manifest to
inspect cgroup limits and verify a CPU-affinity escape is denied. `workloads` runs bounded
`stress-ng` CPU, memory, process, and disk work as that allocation user and creates a temporary
fio file. It requires explicit consent:

```bash
KLOIGOS_VALIDATION_GROUP=workloads \
KLOIGOS_VALIDATION_ALLOW_DESTRUCTIVE=1 \
make validate
```

## Fixtures and controller inputs

Copy [`controller.env.example`](controller.env.example) into an untracked local environment file
or export its settings. The inventory must contain only explicitly designated test hosts. When a
`resources`, `network`, and `workloads` need fixture resources: point
`KLOIGOS_VALIDATION_FIXTURE_MANIFEST` at your manifest and choose an allocation with
`KLOIGOS_VALIDATION_FIXTURE_ALLOCATION`.

For the local demo, provision and later remove those declared resources explicitly:

```bash
make validate ARGS="fixtures setup"
make validate
make validate ARGS="fixtures cleanup"
```

The fixture commands poll every queued allocation or deallocation job to completion and never
discover or alter resources outside the manifest.
