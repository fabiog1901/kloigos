"""Bounded fio and iperf3 workloads with no hardware-independent thresholds."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

def _r(i: str, s: str, m: str) -> dict[str, str]: return {"id": i, "status": s, "summary": m}
def _run(*args: str) -> subprocess.CompletedProcess[str]: return subprocess.run(args, text=True, capture_output=True, timeout=90, check=False)

def collect_storage_network_results(directory: Path, iperf_server: str | None, artifacts: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not directory.is_dir(): return [_r("workloads.input", "error", f"Workload directory '{directory}' does not exist.")]
    artifacts.mkdir(parents=True, exist_ok=True)
    fio = shutil.which("fio")
    if not fio: results.append(_r("storage.fio", "error", "fio is not installed."))
    else:
        test_file = directory / ".kloigos-validation-fio.bin"
        try:
            run = _run(fio, "--name=kloigos-validation", f"--filename={test_file}", "--size=64M", "--rw=readwrite", "--bs=1M", "--iodepth=1", "--direct=0", "--verify=crc32c", "--do_verify=1", "--output-format=json")
            (artifacts / "fio.json").write_text(run.stdout)
            if run.returncode: results.append(_r("storage.fio", "failed", run.stderr.strip() or "fio verification workload failed."))
            else:
                data=json.loads(run.stdout); job=data["jobs"][0]; bw=job["write"]["bw_bytes"] + job["read"]["bw_bytes"]
                results.append(_r("storage.fio", "passed", f"fio verified read/write correctness; measured aggregate bandwidth {bw} B/s."))
        except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc: results.append(_r("storage.fio", "error", f"Unable to run fio: {exc}."))
        finally: test_file.unlink(missing_ok=True)
    if not iperf_server: results.append(_r("network.iperf3", "skipped", "No --iperf-server host:port was supplied.")); return results
    iperf = shutil.which("iperf3")
    if not iperf: results.append(_r("network.iperf3", "error", "iperf3 is not installed.")); return results
    host, sep, port = iperf_server.rpartition(":")
    if not sep or not host or not port.isdigit(): return results + [_r("network.iperf3", "error", "--iperf-server must be host:port.")]
    try:
        run=_run(iperf, "-c", host, "-p", port, "-t", "5", "-J"); (artifacts / "iperf3.json").write_text(run.stdout)
        if run.returncode: results.append(_r("network.iperf3", "failed", run.stderr.strip() or "iperf3 connectivity workload failed."))
        else:
            data=json.loads(run.stdout); bits=data["end"]["sum_sent"]["bits_per_second"]
            results.append(_r("network.iperf3", "passed", f"iperf3 connectivity succeeded; measured transmit throughput {bits:.0f} bit/s."))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc: results.append(_r("network.iperf3", "error", f"Unable to run iperf3: {exc}."))
    return results
