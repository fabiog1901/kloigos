#!/usr/bin/env python3
"""Run Kloigos real-host validation and evaluate its collected evidence."""

from __future__ import annotations
import argparse, json, os, sys, time, uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA_VERSION = 1
GROUPS = frozenset({"smoke", "resources", "network", "workloads"})
DESTRUCTIVE_GROUPS = frozenset({"workloads"})


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def evaluation_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group", required=True, choices=sorted(GROUPS))
    p.add_argument("--target", required=True)
    p.add_argument("--evidence-file", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--allow-destructive", action="store_true")
    return p


def load_evidence(path: Path) -> list[dict[str, str]]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read evidence '{path}': {exc}") from exc
    if not isinstance(value, list):
        raise ValueError("Evidence must be a JSON array.")
    records = []
    for index, item in enumerate(value, 1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ):
            raise ValueError(f"Evidence record {index} needs a non-empty id.")
        if item.get("status") == "skipped":
            records.append(
                {
                    "id": item["id"],
                    "status": "skipped",
                    "summary": str(item.get("summary") or "Not configured."),
                }
            )
            continue
        if not isinstance(item.get("rc"), int):
            raise ValueError(f"Evidence record {index} needs an integer rc.")
        if "expect_failure" in item and not isinstance(item["expect_failure"], bool):
            raise ValueError(
                f"Evidence record {index} expect_failure must be a boolean."
            )
        output = (
            str(
                item.get("stderr") or item.get("stdout") or "command returned no output"
            )
            .strip()
            .replace("\n", " ")
        )
        expected_failure = item.get("expect_failure", False)
        passed = item["rc"] != 0 if expected_failure else item["rc"] == 0
        expectation = (
            "denied as expected"
            if expected_failure and passed
            else "unexpectedly succeeded" if expected_failure else output[:300]
        )
        records.append(
            {
                "id": item["id"],
                "status": "passed" if passed else "failed",
                "summary": f"{item.get('command', item['id'])}: {expectation}",
            }
        )
    return records


def summarize(results: list[dict[str, str]]) -> dict[str, int | str]:
    counts: dict[str, int | str] = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for item in results:
        counts["errors" if item["status"] == "error" else item["status"]] = (
            int(counts["errors" if item["status"] == "error" else item["status"]]) + 1
        )
    counts["status"] = (
        "error" if counts["errors"] else "failed" if counts["failed"] else "passed"
    )
    return counts


def evaluate(argv: Sequence[str]) -> int:
    args = evaluation_parser().parse_args(argv)
    started = timestamp()
    try:
        if args.group in DESTRUCTIVE_GROUPS and not args.allow_destructive:
            raise ValueError(f"{args.group} requires --allow-destructive.")
        results = load_evidence(args.evidence_file)
    except ValueError as exc:
        results = [{"id": "runner.input", "status": "error", "summary": str(exc)}]
    totals = summarize(results)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "id": str(uuid.uuid4()),
            "group": args.group,
            "target": args.target,
            "started_at": started,
            "finished_at": timestamp(),
        },
        "summary": totals,
        "results": results,
        "diagnostics": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"Group: {args.group}\nTarget: {args.target}\nStatus: {totals['status']} (passed={totals['passed']}, failed={totals['failed']}, skipped={totals['skipped']}, errors={totals['errors']})\nReport: {args.output.resolve()}"
    )
    return (
        2 if totals["status"] == "error" else 1 if totals["status"] == "failed" else 0
    )


class ValidationError(Exception):
    """A controller input or remote API error that should return exit status 2."""


def fixture_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import yaml

    try:
        document = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(
            f"Unable to read fixture manifest '{path}': {exc}"
        ) from exc
    if not isinstance(document, dict) or not isinstance(
        document.get("allocations"), list
    ):
        raise ValidationError("Fixture manifest must contain an allocations list.")
    allocations = document["allocations"]
    if not all(isinstance(item, dict) for item in allocations):
        raise ValidationError("Each fixture allocation must be an object.")
    return document, allocations


def api_call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    base_url = os.environ.get("KLOIGOS_VALIDATION_API_URL", "http://localhost:8000/api")
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{method} {path} failed: {exc}") from exc


def wait_for_job(job: Any) -> None:
    if not isinstance(job, dict) or not isinstance(job.get("job_id"), str):
        raise ValidationError("Fixture API response did not contain a job_id.")
    for _ in range(120):
        status = api_call("GET", f"/jobs/{job['job_id']}")
        state = status.get("status") if isinstance(status, dict) else None
        if state == "successful":
            return
        if state in {"failed", "cancelled"}:
            raise ValidationError(f"Fixture job failed: {status}")
        time.sleep(2)
    raise ValidationError(f"Fixture job timed out: {job['job_id']}")


def fixture_addresses(allocations: list[dict[str, Any]]) -> list[str]:
    addresses = [item.get("ip_address") for item in allocations]
    if not all(isinstance(address, str) and address for address in addresses):
        raise ValidationError(
            "Each fixture allocation requires a non-empty ip_address."
        )
    return list(dict.fromkeys(addresses))


def manage_fixtures(action: str) -> int:
    manifest_value = os.environ.get("KLOIGOS_VALIDATION_FIXTURE_MANIFEST")
    if not manifest_value:
        raise ValidationError("KLOIGOS_VALIDATION_FIXTURE_MANIFEST is required.")
    _, allocations = fixture_manifest(Path(manifest_value))
    addresses = fixture_addresses(allocations)
    if action == "setup":
        existing = api_call("GET", "/admin/ip_pool/")
        existing_addresses = {
            item.get("ip_address") for item in existing if isinstance(item, dict)
        }
        addresses_to_add = [
            address for address in addresses if address not in existing_addresses
        ]
        if addresses_to_add:
            api_call("POST", "/admin/ip_pool/", {"ip_addresses": addresses_to_add})
    for allocation in allocations:
        allocation_id = allocation.get("allocation_id")
        if not isinstance(allocation_id, str) or not allocation_id:
            raise ValidationError(
                "Each fixture allocation requires a non-empty allocation_id."
            )
        if action == "setup":
            fields = (
                "allocation_id",
                "login_user",
                "cpu_count",
                "region",
                "zone",
                "tags",
                "ssh_public_key",
            )
            job = api_call(
                "POST",
                "/allocations/",
                {field: allocation.get(field) for field in fields},
            )
        else:
            job = api_call("DELETE", f"/allocations/{allocation_id}")
        wait_for_job(job)
    if action == "cleanup":
        for address in addresses:
            api_call("DELETE", f"/admin/ip_pool/{address}")
    return 0


def selected_fixture(manifest: Path, allocation_id: str) -> dict[str, Any]:
    _, allocations = fixture_manifest(manifest)
    fixture = next(
        (item for item in allocations if item.get("allocation_id") == allocation_id),
        None,
    )
    if fixture is None:
        raise ValidationError(
            "Selected fixture allocation is absent from the manifest."
        )
    return fixture


def run_controller() -> int:
    import ansible_runner

    root = Path(__file__).resolve().parent
    inventory_value = os.environ.get("KLOIGOS_VALIDATION_INVENTORY")
    if not inventory_value or not Path(inventory_value).is_file():
        raise ValidationError(
            "KLOIGOS_VALIDATION_INVENTORY is required and must name a file."
        )
    group = os.environ.get("KLOIGOS_VALIDATION_GROUP", "smoke")
    if group not in GROUPS:
        raise ValidationError(
            f"KLOIGOS_VALIDATION_GROUP must be one of: {', '.join(sorted(GROUPS))}."
        )
    report_dir = Path(
        os.environ.get("KLOIGOS_VALIDATION_REPORT_DIR", root / "reports" / "controller")
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    extravars: dict[str, Any] = {
        "validation_group": group,
        "validation_allow_destructive": os.environ.get(
            "KLOIGOS_VALIDATION_ALLOW_DESTRUCTIVE", "false"
        ),
        "validation_controller_report_dir": str(report_dir),
        "validation_run_id": f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{os.getpid()}",
    }
    manifest_value = os.environ.get("KLOIGOS_VALIDATION_FIXTURE_MANIFEST")
    allocation_id = os.environ.get("KLOIGOS_VALIDATION_FIXTURE_ALLOCATION")
    if group in {"resources", "workloads"} and (
        not manifest_value or not allocation_id
    ):
        raise ValidationError(
            f"{group} requires a fixture manifest and selected allocation."
        )
    if manifest_value and allocation_id:
        extravars["validation_fixture"] = selected_fixture(
            Path(manifest_value), allocation_id
        )
    result = ansible_runner.run(
        private_data_dir=str(root),
        project_dir=str(root / "ansible"),
        playbook="RUN_VALIDATION.yaml",
        inventory=inventory_value,
        extravars=extravars,
    )
    return result.rc


USAGE = 'Usage: make validate [ARGS="run|fixtures setup|fixtures cleanup"]'


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments == ["run"]:
        return run_controller()
    if arguments[0] in {"--help", "-h"}:
        print(
            f"{USAGE}\n\nrun (default) validates explicitly inventoried remote Kloigos test hosts.\nfixtures setup/cleanup manages only allocations and IPs declared in the fixture manifest."
        )
        return 0
    if (
        arguments[0] == "fixtures"
        and len(arguments) == 2
        and arguments[1]
        in {
            "setup",
            "cleanup",
        }
    ):
        return manage_fixtures(arguments[1])
    if arguments[0] == "evaluate":
        return evaluate(arguments[1:])
    raise ValidationError(USAGE)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
