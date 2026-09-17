#!/usr/bin/env python3
"""Run Kloigos real-host validation and evaluate its collected evidence."""

from __future__ import annotations
import argparse, ipaddress, json, os, sys, tarfile, time, uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA_VERSION = 1
GROUPS = frozenset({"all", "smoke", "resources", "network", "workloads"})
DESTRUCTIVE_GROUPS = frozenset({"all", "workloads"})


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def evidence_records(bundle: Path) -> list[dict[str, Any]]:
    """Read remote per-subsection evidence records in deterministic archive order."""
    import yaml

    try:
        with tarfile.open(bundle, "r:gz") as archive:
            members = sorted(
                (
                    item
                    for item in archive.getmembers()
                    if item.isfile()
                    and item.name.lstrip("./").startswith("evidence/")
                    and item.name.lower().endswith((".yaml", ".yml"))
                ),
                key=lambda item: item.name,
            )
            if not members:
                raise ValueError("Evidence bundle contains no per-check YAML records.")
            records: list[dict[str, Any]] = []
            for member in members:
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"Unable to read evidence record '{member.name}'.")
                value = yaml.safe_load(source.read())
                if not isinstance(value, list) or not all(
                    isinstance(item, dict) for item in value
                ):
                    raise ValueError(
                        f"Evidence record '{member.name}' must be a YAML list of objects."
                    )
                records.extend(value)
            return records
    except (OSError, tarfile.TarError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to read evidence bundle '{bundle}': {exc}") from exc


def aggregate_evidence(bundle: Path) -> Path:
    """Write the controller-owned aggregate evidence document for a bundle."""
    import yaml

    output = bundle.with_suffix("").with_suffix(".evidence.yaml")
    output.write_text(yaml.safe_dump(evidence_records(bundle), sort_keys=False))
    return output


def load_evidence(bundle: Path) -> list[dict[str, str]]:
    value = evidence_records(bundle)
    if not isinstance(value, list):
        raise ValueError("Evidence must be a YAML list.")
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


def evaluate(args: argparse.Namespace) -> int:
    started = timestamp()
    aggregate_path: Path | None = None
    try:
        if args.group in DESTRUCTIVE_GROUPS and not args.allow_destructive:
            raise ValueError(f"{args.group} requires --allow-destructive.")
        aggregate_path = aggregate_evidence(args.bundle)
        results = load_evidence(args.bundle)
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
        "diagnostics": [
            {"name": "evidence-bundle", "path": str(args.bundle)},
            *(
                [{"name": "aggregate-evidence", "path": str(aggregate_path)}]
                if aggregate_path is not None
                else []
            ),
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    args.output.write_text(yaml.safe_dump(report, sort_keys=False))
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


def api_call(
    base_url: str, method: str, path: str, body: dict[str, Any] | None = None
) -> Any:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    print(request.data)

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{method} {path} failed: {exc.read()} ") from exc


def wait_for_job(base_url: str, job: Any) -> None:
    if not isinstance(job, dict) or not isinstance(job.get("job_id"), str):
        raise ValidationError("Fixture API response did not contain a job_id.")
    for _ in range(120):
        status = api_call(base_url, "GET", f"/jobs/{job['job_id']}")
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


def manage_fixtures(args: argparse.Namespace) -> int:
    _, allocations = fixture_manifest(args.fixture_manifest)
    addresses = fixture_addresses(allocations)
    if args.action == "setup":
        existing = api_call(args.api_url, "GET", "/admin/ip_pool/")
        existing_addresses = {
            item.get("ip_address") for item in existing if isinstance(item, dict)
        }
        addresses_to_add = [
            address for address in addresses if address not in existing_addresses
        ]
        if addresses_to_add:
            api_call(
                args.api_url,
                "POST",
                "/admin/ip_pool/",
                {"ip_addresses": addresses_to_add},
            )
    for allocation in allocations:
        allocation_id = allocation.get("allocation_id")
        if not isinstance(allocation_id, str) or not allocation_id:
            raise ValidationError(
                "Each fixture allocation requires a non-empty allocation_id."
            )
        if args.action == "setup":
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
                args.api_url,
                "POST",
                "/allocations/",
                {field: allocation.get(field) for field in fields},
            )
        else:
            job = api_call(args.api_url, "DELETE", f"/allocations/{allocation_id}")
        wait_for_job(args.api_url, job)
    if args.action == "cleanup":
        for address in addresses:
            api_call(args.api_url, "DELETE", f"/admin/ip_pool/{address}")
    return 0


def selected_fixture(
    manifest: Path,
    allocation_id: str,
    *,
    require_storage: bool = False,
    require_network: bool = False,
) -> dict[str, Any]:
    _, allocations = fixture_manifest(manifest)
    fixture = next(
        (item for item in allocations if item.get("allocation_id") == allocation_id),
        None,
    )
    if fixture is None:
        raise ValidationError(
            "Selected fixture allocation is absent from the manifest."
        )
    if require_storage:
        for field in ("storage_mount_path", "allocation_mount_path"):
            if not isinstance(fixture.get(field), str) or not fixture[field]:
                raise ValidationError(
                    f"Selected fixture allocation requires a non-empty {field}."
                )
    if require_network:
        for field in (
            "ip_address",
            "network_spoof_ip_address",
            "network_probe_ipv4",
            "network_probe_ipv6",
        ):
            if not isinstance(fixture.get(field), str) or not fixture[field]:
                raise ValidationError(
                    f"Selected fixture allocation requires a non-empty {field}."
                )
        try:
            configured_ip = ipaddress.ip_address(fixture["ip_address"])
            spoof_ip = ipaddress.ip_address(fixture["network_spoof_ip_address"])
            probe_ipv4 = ipaddress.ip_address(fixture["network_probe_ipv4"])
            probe_ipv6 = ipaddress.ip_address(fixture["network_probe_ipv6"])
        except ValueError as exc:
            raise ValidationError(f"Invalid network validation address: {exc}") from exc
        if (
            configured_ip.version != 4
            or spoof_ip.version != 4
            or probe_ipv4.version != 4
        ):
            raise ValidationError(
                "ip_address, network_spoof_ip_address, and network_probe_ipv4 must be IPv4 addresses."
            )
        if probe_ipv6.version != 6:
            raise ValidationError("network_probe_ipv6 must be an IPv6 address.")
        if configured_ip == spoof_ip:
            raise ValidationError(
                "network_spoof_ip_address must differ from the selected allocation ip_address."
            )
        fixture_addresses = {item.get("ip_address") for item in allocations}
        if fixture["network_spoof_ip_address"] not in fixture_addresses:
            raise ValidationError(
                "network_spoof_ip_address must be an ip_address declared by another fixture allocation."
            )
        port = fixture.get("network_probe_port")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValidationError(
                "Selected fixture allocation requires network_probe_port between 1 and 65535."
            )
    peer_id = fixture.get("filesystem_peer_allocation_id") if require_storage else None
    if peer_id is not None:
        if not isinstance(peer_id, str) or not peer_id:
            raise ValidationError(
                "filesystem_peer_allocation_id must be a non-empty allocation ID."
            )
        peer = next(
            (item for item in allocations if item.get("allocation_id") == peer_id), None
        )
        if peer is None:
            raise ValidationError(
                "Selected fixture filesystem_peer_allocation_id is absent from the manifest."
            )
        if (
            not isinstance(peer.get("allocation_mount_path"), str)
            or not peer["allocation_mount_path"]
        ):
            raise ValidationError(
                "Filesystem peer fixture requires a non-empty allocation_mount_path."
            )
        fixture = {**fixture, "filesystem_peer": peer}
    return fixture


def configured(value: Any, environment: str, default: Any = None) -> Any:
    return value if value is not None else os.environ.get(environment, default)


def run_controller(args: argparse.Namespace) -> int:
    import ansible_runner

    root = Path(__file__).resolve().parent

    print(root)

    inventory = configured(args.inventory, "KLOIGOS_VALIDATION_INVENTORY")
    if inventory is None or not Path(inventory).is_file():
        raise ValidationError("--inventory is required and must name a file.")
    group = configured(args.group, "KLOIGOS_VALIDATION_GROUP", "all")
    if group not in GROUPS:
        raise ValidationError(f"--group must be one of: {', '.join(sorted(GROUPS))}.")
    allow_destructive = configured(
        args.allow_destructive, "KLOIGOS_VALIDATION_ALLOW_DESTRUCTIVE", "false"
    )
    if isinstance(allow_destructive, str):
        allow_destructive = allow_destructive.lower() in {"1", "true", "yes"}
    if group in DESTRUCTIVE_GROUPS and not allow_destructive:
        raise ValidationError(
            f"{group} requires --allow-destructive (or KLOIGOS_VALIDATION_ALLOW_DESTRUCTIVE=1)."
        )
    report_dir = Path(
        configured(
            args.report_dir,
            "KLOIGOS_VALIDATION_REPORT_DIR",
            root / "reports",
        )
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{os.getpid()}"
    extravars: dict[str, Any] = {
        "validation_group": group,
        "validation_allow_destructive": allow_destructive,
        "validation_controller_report_dir": str(report_dir),
        "validation_run_id": run_id,
    }
    manifest_value = configured(
        args.fixture_manifest, "KLOIGOS_VALIDATION_FIXTURE_MANIFEST"
    )
    allocation_id = configured(
        args.fixture_allocation, "KLOIGOS_VALIDATION_FIXTURE_ALLOCATION"
    )
    if group in {"all", "resources", "network", "workloads"} and (
        not manifest_value or not allocation_id
    ):
        raise ValidationError(
            f"{group} requires a fixture manifest and selected allocation."
        )
    if manifest_value and allocation_id:
        fixture = selected_fixture(
            Path(manifest_value),
            allocation_id,
            require_storage=group in {"all", "resources", "workloads"},
            require_network=group in {"all", "network"},
        )
        extravars["validation_fixture"] = fixture
        if "filesystem_peer" in fixture:
            extravars["validation_filesystem_peer"] = fixture["filesystem_peer"]

    result = ansible_runner.run(
        private_data_dir=str("/tmp/"),
        project_dir=str(root / "ansible"),
        playbook="RUN_VALIDATION.yaml",
        inventory=str(root / inventory),
        extravars=extravars,
    )
    if result.rc:
        return result.rc
    bundles = sorted(report_dir.glob(f"*-{run_id}.tar.gz"))
    if not bundles:
        raise ValidationError("Ansible completed without fetching an evidence bundle.")
    return max(
        evaluate(
            argparse.Namespace(
                group=group,
                target=bundle.name.removesuffix(f"-{run_id}.tar.gz"),
                bundle=bundle,
                output=bundle.with_suffix("").with_suffix(".report.yaml"),
                allow_destructive=True,
            )
        )
        for bundle in bundles
    )


def add_controller_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inventory",
        type=Path,
        default=None,
        help="Ansible inventory file (fallback: KLOIGOS_VALIDATION_INVENTORY).",
    )
    parser.add_argument(
        "--group",
        choices=sorted(GROUPS),
        default=None,
        help="Check scope; defaults to all (fallback: KLOIGOS_VALIDATION_GROUP).",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory for fetched bundles and YAML reports (fallback: KLOIGOS_VALIDATION_REPORT_DIR).",
    )
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=None,
        help="Fixture manifest (fallback: KLOIGOS_VALIDATION_FIXTURE_MANIFEST).",
    )
    parser.add_argument(
        "--fixture-allocation",
        default=None,
        help="Allocation ID in the fixture manifest (fallback: KLOIGOS_VALIDATION_FIXTURE_ALLOCATION).",
    )
    parser.add_argument(
        "--allow-destructive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow workloads; use --no-allow-destructive to override the environment.",
    )


def add_fixture_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=None,
        help="Fixture manifest (fallback: KLOIGOS_VALIDATION_FIXTURE_MANIFEST).",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Kloigos API URL (fallback: KLOIGOS_VALIDATION_API_URL).",
    )


def add_evaluation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--group", required=True, choices=sorted(GROUPS))
    parser.add_argument("--target", required=True)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-destructive", action="store_true")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="Run checks on explicitly inventoried test hosts."
    )
    add_controller_arguments(run)
    fixtures = commands.add_parser(
        "fixtures", help="Manage manifest-declared fixtures."
    )
    fixture_actions = fixtures.add_subparsers(dest="action", required=True)
    for action in ("setup", "cleanup"):
        fixture_action = fixture_actions.add_parser(action)
        add_fixture_arguments(fixture_action)
    evaluation = commands.add_parser("evaluate", help=argparse.SUPPRESS)
    add_evaluation_arguments(evaluation)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "run":
        return run_controller(args)
    if args.command == "fixtures":
        manifest = configured(
            args.fixture_manifest, "KLOIGOS_VALIDATION_FIXTURE_MANIFEST"
        )
        if manifest is None:
            raise ValidationError("--fixture-manifest is required.")
        args.fixture_manifest = Path(manifest)
        args.api_url = configured(
            args.api_url, "KLOIGOS_VALIDATION_API_URL", "http://localhost:8000/api"
        )
        return manage_fixtures(args)
    return evaluate(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
