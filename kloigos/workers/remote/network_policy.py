"""Remote network-security-group policy reconciliation worker."""

import logging

from cpkit import get_repo
from cpkit.audit import log_event
from cpkit.playbooks import run_playbook

from ...models import (
    Event,
    NetworkPolicyApplyCommand,
    Playbook,
    ServerNotFoundError,
)
from ...services.network_policy import NetworkPolicyService, render_nftables_policy


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


def run_network_policy_apply(
    job_id: int,
    payload: NetworkPolicyApplyCommand,
    actor_id: str,
) -> None:
    """Render and apply the current effective policy for one managed host."""
    repo = get_repo()
    servers = repo.get_servers(payload.hostname)
    if not servers:
        raise ServerNotFoundError(f"Server '{payload.hostname}' was not found.")
    server = servers[0]
    host_policy = NetworkPolicyService(repo).build_host_policy(server.hostname)
    policy = render_nftables_policy(host_policy)
    details = {
        "job_id": job_id,
        "hostname": server.hostname,
        "allocation_count": len(host_policy.allocations),
    }

    try:
        result = run_playbook(
            repo=repo,
            job_id=job_id,
            playbook_name=Playbook.NETWORK_POLICY_APPLY.value,
            extra_vars={
                "hostname": server.hostname,
                "ansible_host": _ansible_host(server.public_ip, server.private_ip),
                "server_admin_user": server.server_admin_user,
                "network_policy_nftables": policy,
            },
        )
        details["playbook_version"] = result.playbook_version
        if result.status == "successful":
            log_event(repo, actor_id, Event.NETWORK_POLICY_APPLY_DONE, details)
            return
        details["error"] = f"Playbook finished with status '{result.status}'."
    except Exception as exc:
        details["error"] = f"Unhandled exception during network policy apply: {exc}"
        logging.exception("Failed to apply network policy for host %s", server.hostname)

    log_event(repo, actor_id, Event.NETWORK_POLICY_APPLY_FAILED, details)
    raise RuntimeError(details["error"])
