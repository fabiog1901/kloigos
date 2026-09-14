"""Scoped, read-only diagnostic collection for failed validation runs."""
from __future__ import annotations
import subprocess
from pathlib import Path

def collect_diagnostics(directory: Path) -> list[dict[str, str]]:
    directory.mkdir(parents=True, exist_ok=True)
    commands={"systemd-failed":["systemctl","--failed","--no-pager"],"journal-tail":["journalctl","-n","200","--no-pager"],"cgroup-tree":["systemd-cgls","--no-pager"],"nftables-ruleset":["nft","list","ruleset"]}
    records=[]
    for name, command in commands.items():
        path=directory/f"{name}.txt"
        try:
            run=subprocess.run(command,text=True,capture_output=True,timeout=20,check=False)
            path.write_text(run.stdout + ("\nSTDERR:\n"+run.stderr if run.stderr else ""))
        except (OSError, subprocess.TimeoutExpired) as exc: path.write_text(f"diagnostic collection failed: {exc}\n")
        records.append({"name":name,"path":str(path.resolve())})
    return records
