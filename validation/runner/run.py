#!/usr/bin/env python3
"""Run the Kloigos real-host validation reporting MVP."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from smoke import collect_smoke_results


SCHEMA_VERSION = 1
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_ERROR = 2
RESULT_STATUSES = frozenset({"passed", "failed", "skipped", "error"})
PROFILE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIRECTORY = ROOT / "profiles"
REPORT_DIRECTORY = ROOT / "reports"
ARTIFACT_DIRECTORY = ROOT / "artifacts"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile name in validation/profiles or path to a profile YAML file.",
    )
    parser.add_argument("--target", required=True, help="Explicit validation-host identifier.")
    parser.add_argument(
        "--results-file",
        type=Path,
        help="JSON array of normalized check-result objects supplied by an adapter.",
    )
    parser.add_argument("--output", type=Path, help="Path for the generated JSON report.")
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow a profile declared as destructive to be selected.",
    )
    return parser


def _profile_path(profile: str) -> Path:
    candidate = Path(profile)
    if candidate.suffix in {".yaml", ".yml"} or candidate.parent != Path("."):
        return candidate
    if not PROFILE_NAME.fullmatch(profile):
        raise ValueError("Profile names must be lowercase hyphen-separated identifiers.")
    return PROFILE_DIRECTORY / f"{profile}.yaml"


def load_profile(profile_argument: str) -> dict[str, Any]:
    path = _profile_path(profile_argument)
    try:
        document = yaml.safe_load(path.read_text())
    except OSError as exc:
        raise ValueError(f"Unable to read profile '{path}': {exc.strerror or exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Profile '{path}' is not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError("A profile must be a YAML mapping.")

    required = {"schema_version", "name", "description", "destructive", "categories", "diagnostics"}
    missing = required - document.keys()
    if missing:
        raise ValueError(f"Profile is missing required field(s): {', '.join(sorted(missing))}.")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported profile schema version: {document['schema_version']!r}.")
    if not isinstance(document["name"], str) or not PROFILE_NAME.fullmatch(document["name"]):
        raise ValueError("Profile 'name' must be a lowercase hyphen-separated identifier.")
    if not isinstance(document["description"], str) or not document["description"].strip():
        raise ValueError("Profile 'description' must be a non-empty string.")
    if not isinstance(document["destructive"], bool):
        raise ValueError("Profile 'destructive' must be a boolean.")
    if not isinstance(document["categories"], list) or not document["categories"]:
        raise ValueError("Profile 'categories' must be a non-empty list.")
    if not all(isinstance(category, str) and category.strip() for category in document["categories"]):
        raise ValueError("Every profile category must be a non-empty string.")
    if document["diagnostics"] not in {"never", "on_failure", "always"}:
        raise ValueError("Profile 'diagnostics' must be never, on_failure, or always.")
    return document


def _normalize_assertion(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("Each assertion must be an object.")
    allowed = {"id", "status", "summary"}
    unexpected = value.keys() - allowed
    if unexpected:
        raise ValueError(f"Assertion contains unsupported field(s): {', '.join(sorted(unexpected))}.")
    normalized = {key: value.get(key) for key in allowed}
    if not isinstance(normalized["id"], str) or not normalized["id"].strip():
        raise ValueError("Assertion 'id' must be a non-empty string.")
    if normalized["status"] not in RESULT_STATUSES:
        raise ValueError("Assertion 'status' must be passed, failed, skipped, or error.")
    if not isinstance(normalized["summary"], str) or not normalized["summary"].strip():
        raise ValueError("Assertion 'summary' must be a non-empty string.")
    return normalized  # type: ignore[return-value]


def normalize_results(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        source = json.loads(path.read_text())
    except OSError as exc:
        raise ValueError(f"Unable to read results file '{path}': {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Results file '{path}' is not valid JSON: {exc.msg}.") from exc
    if not isinstance(source, list):
        raise ValueError("Results file must contain a JSON array.")

    normalized_results: list[dict[str, Any]] = []
    allowed = {"id", "status", "summary", "started_at", "finished_at", "assertions"}
    for index, value in enumerate(source, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"Result {index} must be an object.")
        unexpected = value.keys() - allowed
        if unexpected:
            raise ValueError(
                f"Result {index} contains unsupported field(s): {', '.join(sorted(unexpected))}."
            )
        result = {key: value[key] for key in ("id", "status", "summary") if key in value}
        if not isinstance(result.get("id"), str) or not result["id"].strip():
            raise ValueError(f"Result {index} 'id' must be a non-empty string.")
        if result.get("status") not in RESULT_STATUSES:
            raise ValueError(f"Result {index} 'status' must be passed, failed, skipped, or error.")
        if not isinstance(result.get("summary"), str) or not result["summary"].strip():
            raise ValueError(f"Result {index} 'summary' must be a non-empty string.")
        for field in ("started_at", "finished_at"):
            if field in value:
                if not isinstance(value[field], str) or not value[field].strip():
                    raise ValueError(f"Result {index} '{field}' must be a non-empty string.")
                result[field] = value[field]
        if "assertions" in value:
            if not isinstance(value["assertions"], list):
                raise ValueError(f"Result {index} 'assertions' must be an array.")
            result["assertions"] = [_normalize_assertion(item) for item in value["assertions"]]
        normalized_results.append(result)
    return normalized_results


def summarize(results: list[dict[str, Any]]) -> dict[str, int | str]:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for result in results:
        status = result["status"]
        if status == "error":
            counts["errors"] += 1
        else:
            counts[status] += 1
    status = "error" if counts["errors"] else "failed" if counts["failed"] else "passed"
    return {"status": status, **counts}


def _default_output(profile: str, target: str) -> Path:
    safe_target = re.sub(r"[^A-Za-z0-9_.-]+", "-", target).strip("-") or "target"
    return REPORT_DIRECTORY / f"{_timestamp().replace(':', '')}-{profile}-{safe_target}.json"


def write_report(report: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return output.resolve()


def _exit_status(summary: dict[str, int | str]) -> int:
    return {"passed": EXIT_PASSED, "failed": EXIT_FAILED, "error": EXIT_ERROR}[summary["status"]]  # type: ignore[index]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started_at = _timestamp()
    profile_name = Path(args.profile).stem if Path(args.profile).suffix else args.profile
    results: list[dict[str, Any]]

    try:
        profile = load_profile(args.profile)
        profile_name = profile["name"]
        if profile["destructive"] and not args.allow_destructive:
            raise ValueError("Profile is destructive; rerun with --allow-destructive to select it.")
        results = (
            normalize_results(args.results_file)
            if args.results_file is not None
            else collect_smoke_results()
            if profile_name == "smoke"
            else []
        )
    except ValueError as exc:
        results = [{"id": "runner.input", "status": "error", "summary": str(exc)}]

    summary = summarize(results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "id": str(uuid.uuid4()),
            "profile": profile_name,
            "target": args.target,
            "started_at": started_at,
            "finished_at": _timestamp(),
        },
        "summary": summary,
        "results": results,
        "diagnostics": [],
    }
    output = write_report(report, args.output or _default_output(profile_name, args.target))
    print(f"Profile: {profile_name}")
    print(f"Target: {args.target}")
    print(
        "Status: {status} (passed={passed}, failed={failed}, skipped={skipped}, errors={errors})".format(
            **summary
        )
    )
    print(f"Report: {output}")
    print(f"Artifacts: {ARTIFACT_DIRECTORY.resolve()}")
    return _exit_status(summary)


if __name__ == "__main__":
    raise SystemExit(main())
