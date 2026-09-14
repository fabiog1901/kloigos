"""Bounded positive and negative isolation checks for one allocation user."""
from __future__ import annotations
import ipaddress
import os
import pwd
import subprocess
from pathlib import Path
from typing import Any

def _r(i: str, s: str, m: str) -> dict[str, str]: return {"id": i, "status": s, "summary": m}
def _cmd(*args: str) -> subprocess.CompletedProcess[str]: return subprocess.run(args, text=True, capture_output=True, timeout=10, check=False)
def _as_user(user: str, *args: str) -> subprocess.CompletedProcess[str]: return _cmd("runuser", "-u", user, "--", *args)
def _limit(path: Path) -> str | None:
    try: return path.read_text().strip()
    except OSError: return None
def _outside_cpu(cpus: str | None) -> int | None:
    allowed: set[int] = set()
    for item in (cpus or "").split(","):
        start, _, end = item.partition("-")
        if start.isdigit(): allowed.update(range(int(start), int(end or start) + 1))
    return next((cpu for cpu in range(os.cpu_count() or 0) if cpu not in allowed), None)

def collect_isolation_results(user: str, *, allow_escape_attempts: bool, deny_path: str | None, spoof_ip: str | None, deny_connect: str | None) -> list[dict[str, Any]]:
    try: account = pwd.getpwnam(user)
    except KeyError: return [_r("isolation.input", "error", f"Allocation user '{user}' does not exist.")]
    cgroup = Path(f"/sys/fs/cgroup/user.slice/user-{account.pw_uid}.slice")
    cpus, memory, pids = (_limit(cgroup / name) for name in ("cpuset.cpus.effective", "memory.max", "pids.max"))
    results: list[dict[str, Any]] = []
    results.append(_r("isolation.cpu-affinity", "passed" if cpus else "failed", "Allocation cgroup has an effective CPU set." if cpus else "Allocation cgroup CPU set is unavailable."))
    results.append(_r("isolation.memory-limit", "passed" if memory and memory != "max" else "failed", "Allocation memory limit is finite." if memory and memory != "max" else "Allocation memory limit is not finite."))
    results.append(_r("isolation.pid-limit", "passed" if pids and pids != "max" else "failed", "Allocation PID limit is finite." if pids and pids != "max" else "Allocation PID limit is not finite."))
    affinity = _as_user(user, "taskset", "-pc", "0")
    results.append(_r("isolation.cpu-affinity.positive", "passed" if affinity.returncode == 0 else "failed", "Allocation user can inspect its constrained CPU affinity." if affinity.returncode == 0 else affinity.stderr.strip() or "Unable to inspect allocation CPU affinity."))
    if not allow_escape_attempts:
        results.append(_r("isolation.escape-attempts", "skipped", "Escape attempts require --allow-escape-attempts.")); return results
    outside_cpu = _outside_cpu(cpus)
    if outside_cpu is None:
        results.append(_r("isolation.cpu-affinity.escape", "skipped", "Allocation CPU set spans every online CPU."))
    else:
        probe = _as_user(user, "taskset", "-c", str(outside_cpu), "/bin/true")
        results.append(_r("isolation.cpu-affinity.escape", "passed" if probe.returncode else "failed", "Allocation user cannot escape its CPU set." if probe.returncode else f"Allocation user ran on CPU {outside_cpu} outside its cgroup CPU set."))
    if deny_path:
        probe = _as_user(user, "test", "-r", deny_path)
        results.append(_r("isolation.filesystem-boundary", "passed" if probe.returncode else "failed", "Allocation user cannot read the declared denied path." if probe.returncode else f"Allocation user can read denied path '{deny_path}'."))
    else: results.append(_r("isolation.filesystem-boundary", "skipped", "No --filesystem-deny-path witness was supplied."))
    if spoof_ip:
        try: ipaddress.ip_address(spoof_ip)
        except ValueError: results.append(_r("isolation.source-ip-spoofing", "error", "--spoof-ip is not a valid IP address."))
        else:
            code = "import socket,sys; s=socket.socket(); s.bind((sys.argv[1],0))"
            probe = _as_user(user, "python3", "-c", code, spoof_ip)
            results.append(_r("isolation.source-ip-spoofing", "passed" if probe.returncode else "failed", "Allocation user cannot bind the declared spoof source address." if probe.returncode else f"Allocation user bound spoof address '{spoof_ip}'."))
    else: results.append(_r("isolation.source-ip-spoofing", "skipped", "No --spoof-ip witness was supplied."))
    if deny_connect and ":" in deny_connect:
        host, port = deny_connect.rsplit(":", 1)
        code = "import socket,sys; socket.create_connection((sys.argv[1],int(sys.argv[2])),3)"
        probe = _as_user(user, "python3", "-c", code, host, port)
        results.append(_r("isolation.network-access", "passed" if probe.returncode else "failed", "Allocation user cannot reach the declared denied endpoint." if probe.returncode else f"Allocation user reached denied endpoint '{deny_connect}'."))
    else: results.append(_r("isolation.network-access", "skipped", "No valid --deny-connect host:port witness was supplied."))
    profile = Path(f"/etc/apparmor.d/kloigos-{user}")
    aa = _cmd("aa-status", "--enabled")
    results.append(_r("isolation.apparmor", "passed" if not aa.returncode and profile.exists() else "skipped", "Kloigos AppArmor profile is present and AppArmor is enabled." if not aa.returncode and profile.exists() else "AppArmor is unavailable or no allocation profile is present."))
    return results
