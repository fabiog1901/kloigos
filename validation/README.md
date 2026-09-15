# Kloigos real-host validation

Run manually from a controller that can SSH to explicitly designated Kloigos test hosts:

```bash
make validate
```

The stable check groups are `smoke` (default), `resources`, `network`, and `workloads`.
Set `KLOIGOS_VALIDATION_GROUP` to select one. `resources` uses the manifest-selected allocation
user to inspect its cgroup limits and prove a CPU-affinity escape is rejected. `workloads` runs
bounded `stress-ng` CPU, memory, process, and disk workers as that allocation user and creates a
temporary fio file; it requires `KLOIGOS_VALIDATION_ALLOW_DESTRUCTIVE=1`.

The one fixture manifest is the only environment-specific configuration source. Set
`KLOIGOS_VALIDATION_FIXTURE_MANIFEST` and select an allocation with
`KLOIGOS_VALIDATION_FIXTURE_ALLOCATION`; use `make validate ARGS="fixtures setup"` before a
run and `make validate ARGS="fixtures cleanup"` afterwards when fixtures are needed.

Ansible runs Linux inspection or workload commands on the selected host, saving raw output and
`evidence.json` in a unique remote workspace. `runner/run.py` evaluates that evidence and writes
the structured JSON report. Both files are fetched below `KLOIGOS_VALIDATION_REPORT_DIR`
(`validation/reports/controller` by default). Successful remote workspaces are removed; failed
ones remain for diagnosis.
