#!/usr/bin/env python3
"""Evaluate Ansible-collected Kloigos validation evidence and write a report."""
from __future__ import annotations
import argparse, json, uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
GROUPS = frozenset({"smoke", "resources", "network", "workloads"})
DESTRUCTIVE_GROUPS = frozenset({"workloads"})

def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group", required=True, choices=sorted(GROUPS)); p.add_argument("--target", required=True)
    p.add_argument("--evidence-file", required=True, type=Path); p.add_argument("--output", required=True, type=Path)
    p.add_argument("--allow-destructive", action="store_true")
    return p

def load_evidence(path: Path) -> list[dict[str, str]]:
    try: value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc: raise ValueError(f"Unable to read evidence '{path}': {exc}") from exc
    if not isinstance(value, list): raise ValueError("Evidence must be a JSON array.")
    records = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip(): raise ValueError(f"Evidence record {index} needs a non-empty id.")
        if item.get("status") == "skipped": records.append({"id": item["id"], "status": "skipped", "summary": str(item.get("summary") or "Not configured.")}); continue
        if not isinstance(item.get("rc"), int): raise ValueError(f"Evidence record {index} needs an integer rc.")
        output = str(item.get("stderr") or item.get("stdout") or "command returned no output").strip().replace("\n", " ")
        records.append({"id": item["id"], "status": "passed" if item["rc"] == 0 else "failed", "summary": f"{item.get('command', item['id'])}: {output[:300]}"})
    return records

def summarize(results: list[dict[str, str]]) -> dict[str, int | str]:
    counts: dict[str, int | str] = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for item in results: counts["errors" if item["status"] == "error" else item["status"]] = int(counts["errors" if item["status"] == "error" else item["status"]]) + 1
    counts["status"] = "error" if counts["errors"] else "failed" if counts["failed"] else "passed"
    return counts

def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv); started = timestamp()
    try:
        if args.group in DESTRUCTIVE_GROUPS and not args.allow_destructive: raise ValueError(f"{args.group} requires --allow-destructive.")
        results = load_evidence(args.evidence_file)
    except ValueError as exc: results = [{"id": "runner.input", "status": "error", "summary": str(exc)}]
    totals = summarize(results)
    report: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "run": {"id": str(uuid.uuid4()), "profile": args.group, "target": args.target, "started_at": started, "finished_at": timestamp()}, "summary": totals, "results": results, "diagnostics": []}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Group: {args.group}\nTarget: {args.target}\nStatus: {totals['status']} (passed={totals['passed']}, failed={totals['failed']}, skipped={totals['skipped']}, errors={totals['errors']})\nReport: {args.output.resolve()}")
    return 2 if totals["status"] == "error" else 1 if totals["status"] == "failed" else 0

if __name__ == "__main__": raise SystemExit(main())
