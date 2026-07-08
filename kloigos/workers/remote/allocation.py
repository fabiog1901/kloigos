"""Remote allocation worker handlers."""

import logging

from cpkit import get_repo
from cpkit.audit import log_event
from cpkit.playbooks import run_playbook

from ...models import (
    AllocationCreateCommand,
    AllocationDeallocateCommand,
    AllocationInDB,
    AllocationScaleCommand,
    AllocationStatus,
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitOverview,
    ComputeUnitStatus,
    Event,
    IpAddressStatus,
    NoFreeComputeUnitError,
    Playbook,
)


def _ansible_host(public_ip: str | None, private_ip: str) -> str:
    return public_ip or private_ip


def _get_compute_unit(repo, compute_id: str) -> ComputeUnitOverview:
    matches = repo.get_compute_units(compute_id=compute_id)
    if not matches:
        raise ComputeUnitNotFoundError(f"Compute unit '{compute_id}' does not exist.")
    return matches[0]


def _get_allocation(repo, allocation_id: str) -> AllocationInDB:
    matches = repo.get_allocations(allocation_id=allocation_id)
    if not matches:
        raise ComputeUnitNotFoundError(f"Allocation '{allocation_id}' does not exist.")
    return matches[0]


def _storage_mount_path(cu: ComputeUnitOverview) -> str:
    return f"/mnt/kloigos/{cu.hostname}/cu{cu.ordinal:02d}"


def _model_details(model) -> dict:
    return model.model_dump(mode="json")


def _allocation_audit_details(allocation: AllocationInDB) -> dict:
    return {
        "allocation_id": allocation.allocation_id,
        "login_user": allocation.login_user,
        "ip_address": allocation.ip_address,
        "tags": allocation.tags or {},
    }


def _compute_unit_audit_details(cu: ComputeUnitOverview) -> dict:
    return {
        "compute_id": cu.compute_id,
        "hostname": cu.hostname,
        "ordinal": cu.ordinal,
        "cpu_count": cu.cpu_count,
        "cpu_range": cu.cpu_range,
        "cpu_set": cu.cpu_set,
        "region": cu.region,
        "zone": cu.zone,
    }


def _allocation_placement_audit_details(
    allocation: AllocationInDB,
    cu: ComputeUnitOverview,
) -> dict:
    return {
        **_allocation_audit_details(allocation),
        **_compute_unit_audit_details(cu),
    }


def _record_playbook_version(details: dict, result) -> None:
    details["playbook_version"] = result.playbook_version


def run_compute_unit_allocate(
    job_id: int,
    payload: AllocationCreateCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that prepares a compute unit allocation."""
    repo = get_repo()
    cu = _get_compute_unit(repo, payload.compute_id)
    allocation = _get_allocation(repo, payload.allocation_id)
    details = {"job_id": job_id, **_allocation_placement_audit_details(allocation, cu)}
    job_ok = False

    try:
        result = run_playbook(
            repo=repo,
            job_id=job_id,
            playbook_name=Playbook.ALLOCATION_CREATE.value,
            extra_vars={
                "compute_id": cu.compute_id,
                "hostname": cu.hostname,
                "ansible_host": _ansible_host(
                    cu.server_public_ip, cu.server_private_ip
                ),
                "server_private_ip": cu.server_private_ip,
                "server_public_ip": cu.server_public_ip,
                "server_admin_user": cu.server_admin_user,
                "private_ip": allocation.ip_address,
                "allocation_id": allocation.allocation_id,
                "login_user": allocation.login_user,
                "allocation_ip_address": allocation.ip_address,
                "compute_unit_storage_mount_path": _storage_mount_path(cu),
                "cpu_range": cu.cpu_range,
                "cpu_set": cu.cpu_set,
                "cpu_count": cu.cpu_count,
                "ssh_public_key": payload.ssh_public_key,
            },
        )
        job_ok = result.status == "successful"
        _record_playbook_version(details, result)
    except Exception as exc:
        details["error"] = f"Unhandled exception during allocation playbook: {exc}"
        logging.exception(
            "Unhandled exception during compute unit allocation for %s",
            cu.compute_id,
        )

    final_status = (
        ComputeUnitStatus.ALLOCATED if job_ok else ComputeUnitStatus.ALLOCATION_FAIL
    )
    final_event = (
        Event.ALLOCATION_CREATE_DONE if job_ok else Event.ALLOCATION_CREATE_FAILED
    )
    final_allocation_status = (
        AllocationStatus.ALLOCATED if job_ok else AllocationStatus.ALLOCATION_FAIL
    )
    final_ip_status = IpAddressStatus.ALLOCATED if job_ok else IpAddressStatus.RESERVED

    try:
        repo.update_compute_unit(
            cu.compute_id,
            status=final_status,
        )
        repo.update_allocation(
            allocation.allocation_id,
            status=final_allocation_status,
        )
        repo.update_ip_pool_address(
            allocation.ip_address,
            status=final_ip_status,
            allocation_id=allocation.allocation_id,
            current_host=cu.hostname,
        )
    except Exception:
        logging.exception(
            "Failed to update allocation state for compute unit %s to final status %s",
            cu.compute_id,
            final_status,
        )

    log_event(repo, actor_id, final_event, details)


def run_compute_unit_deallocate(
    job_id: int,
    payload: AllocationDeallocateCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that deallocates a compute unit."""
    repo = get_repo()
    cu = _get_compute_unit(repo, payload.compute_id)
    allocation = _get_allocation(repo, payload.allocation_id)
    details = {"job_id": job_id, **_allocation_placement_audit_details(allocation, cu)}
    job_ok = False

    try:
        result = run_playbook(
            repo=repo,
            job_id=job_id,
            playbook_name=Playbook.ALLOCATION_DELETE.value,
            extra_vars={
                "compute_id": cu.compute_id,
                "hostname": cu.hostname,
                "ansible_host": _ansible_host(
                    cu.server_public_ip, cu.server_private_ip
                ),
                "server_private_ip": cu.server_private_ip,
                "server_public_ip": cu.server_public_ip,
                "server_admin_user": cu.server_admin_user,
                "private_ip": allocation.ip_address,
                "allocation_id": allocation.allocation_id,
                "login_user": allocation.login_user,
                "allocation_ip_address": allocation.ip_address,
                "compute_unit_storage_mount_path": _storage_mount_path(cu),
                "cpu_set": cu.cpu_set,
            },
        )
        job_ok = result.status == "successful"
        _record_playbook_version(details, result)
    except Exception as exc:
        details["error"] = f"Unhandled exception during deallocation playbook: {exc}"
        logging.exception(
            "Unhandled exception during compute unit deallocation for %s",
            cu.compute_id,
        )

    final_status = (
        ComputeUnitStatus.FREE if job_ok else ComputeUnitStatus.DEALLOCATION_FAIL
    )
    final_event = Event.DEALLOCATION_DONE if job_ok else Event.DEALLOCATION_FAILED

    try:
        repo.update_compute_unit(cu.compute_id, status=final_status)
        if job_ok:
            repo.clear_allocation_placement(
                allocation.allocation_id,
                status=AllocationStatus.DEALLOCATED,
            )
            repo.release_ip_pool_address(allocation.ip_address)
        else:
            repo.update_allocation(
                allocation.allocation_id,
                status=AllocationStatus.DEALLOCATION_FAIL,
            )
            repo.update_ip_pool_address(
                allocation.ip_address,
                status=IpAddressStatus.ALLOCATED,
                allocation_id=allocation.allocation_id,
                current_host=cu.hostname,
            )
    except Exception:
        logging.exception(
            "Failed to update deallocation state for compute unit %s to final status %s",
            cu.compute_id,
            final_status,
        )
    log_event(repo, actor_id, final_event, details)


def run_allocation_scale(
    job_id: int,
    payload: AllocationScaleCommand,
    actor_id: str,
) -> None:
    """Run the remote playbook job that scales an allocation placement."""
    repo = get_repo()
    allocation = _get_allocation(repo, payload.allocation_id)
    if allocation.compute_id is None:
        raise ComputeUnitOperationError(
            f"Allocation '{payload.allocation_id}' has no active compute unit."
        )
    source = _get_compute_unit(repo, allocation.compute_id)
    try:
        target = repo.lock_compute_unit(
            compute_id=payload.compute_id,
            region=payload.region,
            zone=payload.zone,
            cpu_count=payload.cpu_count,
            free_status=ComputeUnitStatus.FREE,
            allocated_status=ComputeUnitStatus.ALLOCATING,
        )
        if not target:
            repo.update_allocation(
                payload.allocation_id,
                status=AllocationStatus.SCALE_FAIL,
            )
            raise NoFreeComputeUnitError(
                "No free target compute unit found for allocation scale request."
            )
    except Exception as exc:
        details = {
            "job_id": job_id,
            **_allocation_audit_details(allocation),
            "source_compute_unit": _compute_unit_audit_details(source),
            "request": _model_details(payload),
            "error": str(exc),
        }
        log_event(repo, actor_id, Event.ALLOCATION_SCALE_FAILED, details)
        raise

    details = {
        "job_id": job_id,
        **_allocation_audit_details(allocation),
        "source_compute_unit": _compute_unit_audit_details(source),
        "target_compute_unit": _compute_unit_audit_details(target),
        "request": _model_details(payload),
    }

    try:
        result = run_playbook(
            repo=repo,
            job_id=job_id,
            playbook_name=Playbook.ALLOCATION_SCALE.value,
            extra_vars={
                "allocation_id": allocation.allocation_id,
                "login_user": allocation.login_user,
                "allocation_ip_address": allocation.ip_address,
                "private_ip": allocation.ip_address,
                "source_compute_id": source.compute_id,
                "source_hostname": source.hostname,
                "source_ansible_host": _ansible_host(
                    source.server_public_ip,
                    source.server_private_ip,
                ),
                "source_server_private_ip": source.server_private_ip,
                "source_server_public_ip": source.server_public_ip,
                "source_server_admin_user": source.server_admin_user,
                "source_storage_mount_path": _storage_mount_path(source),
                "source_cpu_range": source.cpu_range,
                "source_cpu_set": source.cpu_set,
                "target_compute_id": target.compute_id,
                "target_hostname": target.hostname,
                "target_ansible_host": _ansible_host(
                    target.server_public_ip,
                    target.server_private_ip,
                ),
                "target_server_private_ip": target.server_private_ip,
                "target_server_public_ip": target.server_public_ip,
                "target_server_admin_user": target.server_admin_user,
                "target_storage_mount_path": _storage_mount_path(target),
                "target_cpu_range": target.cpu_range,
                "target_cpu_set": target.cpu_set,
                "target_cpu_count": target.cpu_count,
            },
        )
        job_ok = result.status == "successful"
        _record_playbook_version(details, result)
    except Exception as exc:
        job_ok = False
        details["error"] = f"Unhandled exception during scale playbook: {exc}"
        logging.exception(
            "Unhandled exception during allocation scale for %s",
            allocation.allocation_id,
        )

    if job_ok:
        repo.update_compute_unit(
            source.compute_id, status=ComputeUnitStatus.FREE, tags={}
        )
        repo.update_compute_unit(
            target.compute_id,
            status=ComputeUnitStatus.ALLOCATED,
            tags=allocation.tags or {},
        )
        repo.update_allocation(
            allocation.allocation_id,
            status=AllocationStatus.ALLOCATED,
            compute_id=target.compute_id,
            current_host=target.hostname,
        )
        repo.update_ip_pool_address(
            allocation.ip_address,
            status=IpAddressStatus.ALLOCATED,
            allocation_id=allocation.allocation_id,
            current_host=target.hostname,
        )
        event = Event.ALLOCATION_SCALE_DONE
    else:
        repo.update_compute_unit(
            target.compute_id,
            status=ComputeUnitStatus.ALLOCATION_FAIL,
            tags={},
        )
        repo.update_allocation(
            allocation.allocation_id,
            status=AllocationStatus.SCALE_FAIL,
            compute_id=source.compute_id,
            current_host=source.hostname,
        )
        repo.update_ip_pool_address(
            allocation.ip_address,
            status=IpAddressStatus.ALLOCATED,
            allocation_id=allocation.allocation_id,
            current_host=source.hostname,
        )
        event = Event.ALLOCATION_SCALE_FAILED

    log_event(repo, actor_id, event, details)
