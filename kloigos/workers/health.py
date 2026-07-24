"""Server health check queue handler."""

import logging
import subprocess
from dataclasses import dataclass
from typing import Any

from cpkit.repository import get_repo

from ..models import (
    AlertSeverity,
    AlertType,
    ServerHealthStatus,
    ServerInDB,
    ServerStatus,
)

logger = logging.getLogger(__name__)

SSH_CONNECT_TIMEOUT_SECONDS = 5
SSH_COMMAND_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class HealthProbeResult:
    status: ServerHealthStatus
    message: str
    details: dict[str, str | int | None]


def run_server_health_check(
    _job_id: int,
    _command: Any,
    _requested_by: str,
) -> None:
    """Run one health check cycle."""
    repo = get_repo()
    servers = [
        server for server in repo.get_servers() if server.status == ServerStatus.READY
    ]
    if not servers:
        return

    logger.info("Checking health for %s ready server(s)", len(servers))
    for server in servers:
        try:
            result = _probe_server(server)
            repo.update_server_health(
                server.hostname,
                result.status,
                None if result.status == ServerHealthStatus.HEALTHY else result.message,
            )
            if result.status == ServerHealthStatus.HEALTHY:
                repo.resolve_alert(
                    alert_type=AlertType.SERVER_UNHEALTHY,
                    resource_type="server",
                    resource_id=server.hostname,
                    message=f"Server {server.hostname} is healthy.",
                    details=result.details,
                )
                logger.info("Server %s health check passed", server.hostname)
            else:
                repo.open_or_touch_alert(
                    alert_type=AlertType.SERVER_UNHEALTHY,
                    severity=(
                        AlertSeverity.CRITICAL
                        if result.status == ServerHealthStatus.UNREACHABLE
                        else AlertSeverity.WARNING
                    ),
                    resource_type="server",
                    resource_id=server.hostname,
                    message=result.message,
                    details=result.details,
                )
                logger.warning(
                    "Server %s health check reported %s: %s",
                    server.hostname,
                    result.status,
                    result.message,
                )
        except Exception:
            logger.exception("Server %s health check failed", server.hostname)


def _probe_server(server: ServerInDB) -> HealthProbeResult:
    target_host = server.private_ip or server.hostname
    target = f"{server.server_admin_user}@{target_host}"
    command = "sudo -n true && " "test -d /mnt/kloigos && " "command -v nft >/dev/null"
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SECONDS}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        target,
        command,
    ]

    try:
        completed = subprocess.run(
            ssh,
            capture_output=True,
            check=False,
            text=True,
            timeout=SSH_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return HealthProbeResult(
            status=ServerHealthStatus.UNREACHABLE,
            message=f"Server {server.hostname} health check timed out.",
            details={
                "hostname": server.hostname,
                "target": target,
                "timeout_seconds": SSH_COMMAND_TIMEOUT_SECONDS,
            },
        )
    except OSError as exc:
        return HealthProbeResult(
            status=ServerHealthStatus.UNREACHABLE,
            message=f"Server {server.hostname} health check could not start: {exc}.",
            details={
                "hostname": server.hostname,
                "target": target,
                "error": str(exc),
            },
        )

    details = {
        "hostname": server.hostname,
        "target": target,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip() or None,
        "stderr": completed.stderr.strip() or None,
    }
    if completed.returncode == 0:
        return HealthProbeResult(
            status=ServerHealthStatus.HEALTHY,
            message=f"Server {server.hostname} is healthy.",
            details=details,
        )

    return HealthProbeResult(
        status=ServerHealthStatus.UNREACHABLE,
        message=f"Server {server.hostname} failed health check.",
        details=details,
    )
