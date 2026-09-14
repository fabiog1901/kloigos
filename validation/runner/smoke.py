"""Read-only configured-state checks for a Kloigos validation host."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


SYSTEMD_DIRECTORY = Path("/etc/systemd/system")
NFT_DIRECTORY = Path("/etc/nftables.d")
KLOIGOS_MOUNT_ROOT = Path("/mnt/kloigos")


def _result(check_id: str, status: str, summary: str) -> dict[str, str]:
    return {"id": check_id, "status": status, "summary": summary}


def _command(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)


def _config_value(path: Path, key: str) -> str | None:
    for line in path.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _compute_units() -> dict[str, str]:
    try:
        volumes = _command("lvs", "--noheadings", "-o", "lv_name")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return _result("compute-units.discovery", "error", f"Unable to inspect LVM compute units: {exc}.")
    names = [line.strip() for line in volumes.stdout.splitlines() if re.fullmatch(r"cu\d+", line.strip())]
    if volumes.returncode:
        return _result("compute-units.discovery", "error", volumes.stderr.strip() or "lvs failed.")
    if not names:
        return _result("compute-units.discovery", "failed", "No Kloigos compute-unit logical volumes were found.")
    return _result("compute-units.discovery", "passed", f"Found {len(names)} compute-unit logical volume(s).")


def _cgroup_controllers() -> dict[str, str]:
    controllers = Path("/sys/fs/cgroup/cgroup.controllers")
    delegate = SYSTEMD_DIRECTORY / "user@.service.d/delegate.conf"
    if not controllers.exists():
        return _result("cgroups.v2", "failed", "The cgroup v2 controller file is absent.")
    required = {"cpuset", "cpu", "io", "memory", "pids"}
    available = set(controllers.read_text().split())
    missing = sorted(required - available)
    if missing:
        return _result("cgroups.v2", "failed", f"Missing cgroup v2 controller(s): {', '.join(missing)}.")
    if not delegate.exists():
        return _result("cgroups.v2", "failed", "Kloigos user-service delegation configuration is absent.")
    delegated = _config_value(delegate, "DelegateControllers")
    if delegated is None or required - set(delegated.split()):
        return _result("cgroups.v2", "failed", "Kloigos delegation does not include all required controllers.")
    return _result("cgroups.v2", "passed", "cgroup v2 and Kloigos controller delegation are configured.")


def _cpu_cpuset() -> dict[str, str]:
    overrides = sorted(SYSTEMD_DIRECTORY.glob("user-*.slice.d/50-kloigos.conf"))
    if not overrides:
        return _result("cpu.cpuset", "skipped", "No allocated-user slice overrides are present on this host.")
    invalid: list[str] = []
    for override in overrides:
        allowed_cpus = _config_value(override, "AllowedCPUs")
        accounting = [_config_value(override, key) for key in ("CPUAccounting", "MemoryAccounting", "IOAccounting")]
        if not allowed_cpus or accounting != ["yes", "yes", "yes"]:
            invalid.append(str(override))
    if invalid:
        return _result("cpu.cpuset", "failed", f"Invalid CPU/cpuset slice override(s): {', '.join(invalid)}.")
    return _result("cpu.cpuset", "passed", f"Validated CPU/cpuset configuration for {len(overrides)} allocation(s).")


def _systemd() -> dict[str, str]:
    try:
        manager = _command("systemctl", "show", "--property=Version", "--value")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return _result("systemd.manager", "error", f"Unable to inspect systemd: {exc}.")
    if manager.returncode or not manager.stdout.strip():
        return _result("systemd.manager", "failed", "systemd manager properties are unavailable.")
    return _result("systemd.manager", "passed", f"systemd manager is available (version {manager.stdout.strip()}).")


def _storage() -> dict[str, str]:
    mounts = [path for path in KLOIGOS_MOUNT_ROOT.glob("*/cu*") if path.is_dir()]
    if not mounts:
        return _result("storage.compute-unit-mounts", "failed", "No Kloigos compute-unit mount directories were found.")
    unmounted: list[str] = []
    for mount in mounts:
        try:
            status = _command("findmnt", "--target", str(mount), "--noheadings")
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return _result("storage.compute-unit-mounts", "error", f"Unable to inspect mounts: {exc}.")
        if status.returncode:
            unmounted.append(str(mount))
    if unmounted:
        return _result("storage.compute-unit-mounts", "failed", f"Unmounted compute-unit path(s): {', '.join(unmounted)}.")
    return _result("storage.compute-unit-mounts", "passed", f"Validated {len(mounts)} compute-unit mount(s).")


def _networking() -> dict[str, str]:
    floating_directory = Path("/etc/kloigos/floating-ips.d")
    configurations = sorted(floating_directory.glob("*.conf")) if floating_directory.exists() else []
    if not configurations:
        return _result("networking.floating-ips", "skipped", "No Kloigos floating-IP configurations are present.")
    missing: list[str] = []
    for configuration in configurations:
        address = _config_value(configuration, "ip_address")
        if not address:
            missing.append(f"{configuration} (missing ip_address)")
            continue
        try:
            configured = _command("ip", "addr", "show", "to", address)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return _result("networking.floating-ips", "error", f"Unable to inspect IP addresses: {exc}.")
        if configured.returncode:
            missing.append(address)
    if missing:
        return _result("networking.floating-ips", "failed", f"Missing floating IP configuration(s): {', '.join(missing)}.")
    return _result("networking.floating-ips", "passed", f"Validated {len(configurations)} floating-IP configuration(s).")


def _nftables() -> dict[str, str]:
    main_configuration = Path("/etc/nftables.conf")
    compute_units = NFT_DIRECTORY / "kloigos-compute-units.nft"
    if not main_configuration.exists() or not compute_units.exists():
        return _result("nftables.configuration", "failed", "Kloigos nftables configuration files are absent.")
    if 'include "/etc/nftables.d/*.nft"' not in main_configuration.read_text():
        return _result("nftables.configuration", "failed", "nftables.conf does not include the Kloigos rule directory.")
    try:
        validation = _command("nft", "-c", "-f", str(compute_units))
        table = _command("nft", "list", "table", "inet", "kloigos_compute_units")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return _result("nftables.configuration", "error", f"Unable to inspect nftables: {exc}.")
    if validation.returncode:
        return _result("nftables.configuration", "failed", validation.stderr.strip() or "nftables syntax validation failed.")
    if table.returncode:
        return _result("nftables.configuration", "failed", "Kloigos compute-unit nftables table is not active.")
    return _result("nftables.configuration", "passed", "Kloigos nftables configuration validates and is active.")


def _apparmor() -> dict[str, str]:
    profiles = sorted(Path("/etc/apparmor.d").glob("kloigos-*"))
    try:
        enabled = _command("aa-status", "--enabled")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _result("apparmor.profiles", "skipped", "AppArmor inspection is unavailable on this target platform.")
    if enabled.returncode:
        return _result("apparmor.profiles", "failed", "AppArmor is installed but not enabled.")
    if not profiles:
        return _result("apparmor.profiles", "skipped", "No Kloigos AppArmor profiles are present.")
    return _result("apparmor.profiles", "passed", f"AppArmor is enabled with {len(profiles)} Kloigos profile(s).")


def _resource_limits() -> dict[str, str]:
    overrides = sorted(SYSTEMD_DIRECTORY.glob("user@*.service.d/50-kloigos.conf"))
    if not overrides:
        return _result("resource-limits.nofile", "skipped", "No allocation LimitNOFILE overrides are present.")
    invalid = [str(path) for path in overrides if not (_config_value(path, "LimitNOFILE") or "").isdigit()]
    if invalid:
        return _result("resource-limits.nofile", "failed", f"Invalid LimitNOFILE override(s): {', '.join(invalid)}.")
    return _result("resource-limits.nofile", "passed", f"Validated LimitNOFILE rendering for {len(overrides)} allocation(s).")


def collect_smoke_results() -> list[dict[str, str]]:
    """Return all read-only smoke-check results without raising host-state failures."""
    checks = (
        _compute_units,
        _cgroup_controllers,
        _cpu_cpuset,
        _systemd,
        _storage,
        _networking,
        _nftables,
        _apparmor,
        _resource_limits,
    )
    results: list[dict[str, str]] = []
    for check in checks:
        try:
            results.append(check())
        except (OSError, UnicodeError, ValueError) as exc:
            results.append(_result(f"{check.__name__[1:]}.unexpected", "error", str(exc)))
    return results
