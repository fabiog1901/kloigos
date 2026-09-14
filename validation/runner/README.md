# Validation runner

`run.py` is the local orchestration and reporting entry point for Kloigos real-host validation. It
selects a declarative profile, normalizes supplied check results, writes a JSON report conforming to
`../report.schema.json`, and prints a concise terminal summary.

The runner does not yet perform host checks by itself. Later profile phases provide the adapters
that gather and submit results. This separation keeps the MVP safe to run while making the result
and exit-status contract available now.

## Usage

Run a named profile from `validation/profiles/` against an explicitly named target:

```bash
python3 validation/runner/run.py --profile smoke --target validation-host-01
```

The command writes a timestamped report under `validation/reports/` by default. Use `--output` to
choose a different report path.

For adapter development, `--results-file` accepts a JSON array of normalized result objects. Each
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
