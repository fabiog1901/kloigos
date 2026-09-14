"""Bounded simultaneous stress-ng workloads for explicitly selected allocation users."""
from __future__ import annotations
import pwd
import shutil
import subprocess
from pathlib import Path
from typing import Any

def _r(i: str,s: str,m: str)->dict[str,str]: return {"id":i,"status":s,"summary":m}
def collect_concurrent_stress_results(users: list[str], seconds: int, iperf_server: str | None, artifacts: Path)->list[dict[str,Any]]:
    if len(users)<2:return [_r("contention.input","error","Concurrent stress requires at least two allocation users.")]
    if not 1<=seconds<=60:return [_r("contention.input","error","--stress-seconds must be between 1 and 60.")]
    if not shutil.which("stress-ng"):return [_r("contention.stress-ng","error","stress-ng is not installed.")]
    artifacts.mkdir(parents=True,exist_ok=True); jobs=[]; results=[]
    for user in users:
        try: pwd.getpwnam(user)
        except KeyError: return [_r("contention.input","error",f"Allocation user '{user}' does not exist.")]
        log=(artifacts/f"stress-ng-{user}.log").open("w")
        jobs.append((user,log,subprocess.Popen(["runuser","-u",user,"--","stress-ng","--cpu","1","--vm","1","--vm-bytes","64M","--fork","1","--hdd","1","--hdd-bytes","16M","--timeout",f"{seconds}s","--metrics-brief"],stdout=log,stderr=subprocess.STDOUT,text=True)))
    failures=[]
    for user,log,job in jobs:
        code=job.wait(timeout=seconds+30); log.close()
        if code: failures.append(user)
    results.append(_r("contention.cpu-memory-process-disk","passed" if not failures else "failed",f"Completed bounded simultaneous stress for {len(users)} allocation users." if not failures else f"stress-ng failed for: {', '.join(failures)}."))
    if iperf_server:
        host, sep, port = iperf_server.rpartition(":")
        if not shutil.which("iperf3") or not sep or not port.isdigit(): results.append(_r("contention.network","error","iperf3 or a valid --iperf-server host:port is required."))
        else:
            network=[(user,subprocess.Popen(["runuser","-u",user,"--","iperf3","-c",host,"-p",port,"-t",str(seconds),"-J"],stdout=(artifacts/f"iperf3-{user}.json").open("w"),stderr=subprocess.STDOUT,text=True)) for user in users]
            network_failures=[user for user,job in network if job.wait(timeout=seconds+30)]
            results.append(_r("contention.network","passed" if not network_failures else "failed", "Concurrent iperf3 connectivity workloads completed." if not network_failures else f"iperf3 failed for: {', '.join(network_failures)}."))
    cgroups=[]
    for user in users:
        uid=pwd.getpwnam(user).pw_uid; path=Path(f"/sys/fs/cgroup/user.slice/user-{uid}.slice/cpuset.cpus.effective")
        if path.exists(): cgroups.append(path.read_text().strip())
    results.append(_r("contention.isolation","passed" if len(cgroups)==len(users) and len(set(cgroups))==len(cgroups) else "failed", "Allocation CPU sets remain distinct." if len(cgroups)==len(users) and len(set(cgroups))==len(cgroups) else "Allocation cgroup CPU sets are missing or overlap."))
    state=subprocess.run(["systemctl","is-system-running"],capture_output=True,text=True,timeout=10)
    results.append(_r("contention.host-responsiveness","passed" if state.stdout.strip() in {"running","degraded"} else "failed",f"Host remains {state.stdout.strip() or 'unresponsive'} after stress."))
    if not iperf_server: results.append(_r("contention.network","skipped","No --iperf-server was supplied for network contention measurement."))
    return results
