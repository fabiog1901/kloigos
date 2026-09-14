# Validation runner

`run.py` is the local orchestration and reporting entry point for Kloigos real-host validation. It
selects a declarative profile, normalizes supplied check results, writes a JSON report conforming to
`../report.schema.json`, and prints a concise terminal summary.

The `smoke` profile performs read-only configured-state checks on the host where the runner runs.
Later profile phases add enforcement, workload, and contention adapters. This separation keeps the
runner safe while making the result and exit-status contract available now.

## Usage

Run a named profile from `validation/profiles/` against an explicitly named target:

```bash
python3 validation/runner/run.py --profile smoke --target validation-host-01
```

Run this command on the prepared validation host (for example through an explicitly initiated SSH
session). `--target` is a report label and does not establish a remote connection.

The command writes a timestamped report under `validation/reports/` by default. Use `--output` to
choose a different report path.

For adapter development or to override the built-in smoke adapter, `--results-file` accepts a JSON array of normalized result objects. Each
object has `id`, `status`, and `summary`, with optional `started_at`, `finished_at`, and
`assertions`. Status is one of `passed`, `failed`, `skipped`, or `error`. Unknown fields and invalid
values are rejected and recorded as a runner error in the output report.

```bash
python3 validation/runner/run.py \
  --profile smoke \
  --target validation-host-01 \
  --results-file validation/examples/results.json \
  --output validation/reports/smoke-validation-host-01.json
```

Profiles marked `destructive: true` require `--allow-destructive`. This is an explicit safety gate;
it does not itself run destructive work.

## Exit statuses

- `0`: all checks passed or were skipped.
- `1`: one or more checks failed.
- `2`: a runner, profile, or input error occurred.

The JSON report remains the authoritative interface for automation. Terminal text reports the
profile, target, final status, result counts, report path, and artifact directory.

## Isolation enforcement

`isolation-enforcement` requires `--allow-destructive --allocation-user USER`. Add
`--allow-escape-attempts` to run bounded negative probes. Provide explicit witnesses with
`--filesystem-deny-path`, `--spoof-ip`, and `--deny-connect host:port`; missing witnesses are
reported as skipped. The probes only inspect permissions, bind a socket without sending traffic,
or make the explicitly requested connection.

## Storage and network workloads

`storage-network` requires `--allow-destructive --workload-dir PATH`. It writes and verifies a
64 MiB temporary fio file, removes it afterwards, and preserves fio JSON under artifacts. Supply
`--iperf-server host:port` to run a five-second iperf3 measurement; connectivity and measured
throughput are reported without a hardware-independent performance threshold.
