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
   per-group YAML evidence records immediately under `evidence/` in that workspace.
4. Ansible archives the complete workspace as a `.tar.gz` bundle and fetches it to the selected
   report directory (default: `validation/reports/controller`). The bundle is the immutable audit
   artifact for that host and run.
5. The local `report.py` reads each fetched bundle, aggregates its ordered per-group records into
   adjacent `*.evidence.yaml`, evaluates them, and writes the human-readable YAML report (for
   example, `k01-<run-id>.report.yaml`). It determines the final validation exit status; no
   reporting code is copied to the remote host.

Each remote evidence file is written as soon as its check group completes. This prevents an `all`
run from replacing earlier results and preserves completed diagnostics in the archived workspace if
a later group fails. The controller owns the aggregate evidence document, so it is derived only from
the fetched immutable bundle.

`ansible/PREPARE_VALIDATION_HOST.yaml` is an administrator preparation aid. It is not part of a
normal validation run.

## Check groups

`--group` defaults to `all`, which runs every check group: `smoke`, `resources`, `network`, and
`workloads`. Set it to one of those individual groups to run only that bounded subset.
`resources` uses the allocation selected from the fixture manifest to
inspect cgroup limits and verify a CPU-affinity escape is denied. `workloads` runs bounded
`stress-ng` CPU, memory, process, and disk work as that allocation user and creates a temporary
fio file. Because `all` includes workloads, the default run requires explicit consent:

```bash
make validate ARGS="--allow-destructive --fixture-manifest /path/to/fixtures.yaml --fixture-allocation validation-a"
```

## CLI inputs and fixtures

Use `make validate ARGS="--help"` to see the CLI options. The inventory must contain only
explicitly designated test hosts. The normal all-groups run needs `--inventory`,
`--fixture-manifest`, `--fixture-allocation`, and `--allow-destructive`; `--report-dir` selects
where fetched bundles and YAML reports are retained. Command-line values override their matching
`KLOIGOS_VALIDATION_*` environment variables, which remain available as fallbacks.

For the local demo, provision and later remove those declared resources explicitly:

```bash
make validate ARGS="fixtures setup --fixture-manifest /path/to/fixtures.yaml"
make validate ARGS="--inventory validation/inventory.ini --fixture-manifest /path/to/fixtures.yaml --fixture-allocation validation-a --allow-destructive"
make validate ARGS="fixtures cleanup --fixture-manifest /path/to/fixtures.yaml"
```

The fixture commands poll every queued allocation or deallocation job to completion and never
discover or alter resources outside the manifest.
