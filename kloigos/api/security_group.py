from cpkit import get_audit_actor, require_readonly, require_user
from fastapi import APIRouter, Depends, HTTPException, Response, Security, status

from ..dep import get_security_group_service
from ..models import (
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    SecurityGroupAttachmentInDB,
    SecurityGroupCreateRequest,
    SecurityGroupDetail,
    SecurityGroupInDB,
    SecurityGroupNotFoundError,
    SecurityGroupRuleCreateRequest,
    SecurityGroupRuleInDB,
    SecurityGroupUpdateRequest,
)
from ..services.security_group import SecurityGroupService

router = APIRouter(
    prefix="/security-groups",
    tags=["security-groups"],
)

allocation_router = APIRouter(
    prefix="/allocations",
    tags=["allocation-security-groups"],
)


@router.post(
    "/",
    response_model=SecurityGroupDetail,
    dependencies=[Security(require_user)],
)
async def create_security_group(
    req: SecurityGroupCreateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> SecurityGroupDetail:
    """Create a reusable network security group."""
    try:
        return service.create_security_group(actor_id, req)
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/",
    response_model=list[SecurityGroupInDB],
    dependencies=[Security(require_readonly)],
)
async def list_security_groups(
    service: SecurityGroupService = Depends(get_security_group_service),
) -> list[SecurityGroupInDB]:
    """List network security groups."""
    return service.list_security_groups()


@router.get(
    "/{security_group_id}",
    response_model=SecurityGroupDetail,
    dependencies=[Security(require_readonly)],
)
async def get_security_group(
    security_group_id: str,
    service: SecurityGroupService = Depends(get_security_group_service),
) -> SecurityGroupDetail:
    """Fetch one network security group with rules and attachments."""
    try:
        return service.get_security_group(security_group_id)
    except SecurityGroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/{security_group_id}",
    response_model=SecurityGroupDetail,
    dependencies=[Security(require_user)],
)
async def update_security_group(
    security_group_id: str,
    req: SecurityGroupUpdateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> SecurityGroupDetail:
    """Update a network security group's metadata."""
    try:
        return service.update_security_group(actor_id, security_group_id, req)
    except SecurityGroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{security_group_id}",
    dependencies=[Security(require_user)],
)
async def delete_security_group(
    security_group_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> Response:
    """Delete an unattached network security group."""
    try:
        deleted = service.delete_security_group(actor_id, security_group_id)
    except SecurityGroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security group '{security_group_id}' was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{security_group_id}/rules",
    response_model=SecurityGroupRuleInDB,
    dependencies=[Security(require_user)],
)
async def add_security_group_rule(
    security_group_id: str,
    req: SecurityGroupRuleCreateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> SecurityGroupRuleInDB:
    """Add an allow rule to a network security group."""
    try:
        return service.add_rule(actor_id, security_group_id, req)
    except SecurityGroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{security_group_id}/rules/{rule_id}",
    dependencies=[Security(require_user)],
)
async def delete_security_group_rule(
    security_group_id: str,
    rule_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> Response:
    """Delete one rule from a network security group."""
    try:
        deleted = service.delete_rule(actor_id, security_group_id, rule_id)
    except SecurityGroupNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security group rule '{rule_id}' was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@allocation_router.get(
    "/{allocation_id}/security-groups",
    response_model=list[SecurityGroupDetail],
    dependencies=[Security(require_readonly)],
)
async def list_allocation_security_groups(
    allocation_id: str,
    service: SecurityGroupService = Depends(get_security_group_service),
) -> list[SecurityGroupDetail]:
    """List network security groups attached to an allocation."""
    try:
        return service.list_allocation_security_groups(allocation_id)
    except ComputeUnitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@allocation_router.post(
    "/{allocation_id}/security-groups/{security_group_id}",
    response_model=SecurityGroupAttachmentInDB,
    dependencies=[Security(require_user)],
)
async def attach_security_group(
    allocation_id: str,
    security_group_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> SecurityGroupAttachmentInDB:
    """Attach a network security group to an allocation."""
    try:
        return service.attach_to_allocation(
            actor_id,
            allocation_id,
            security_group_id,
        )
    except (ComputeUnitNotFoundError, SecurityGroupNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@allocation_router.delete(
    "/{allocation_id}/security-groups/{security_group_id}",
    dependencies=[Security(require_user)],
)
async def detach_security_group(
    allocation_id: str,
    security_group_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: SecurityGroupService = Depends(get_security_group_service),
) -> Response:
    """Detach a network security group from an allocation."""
    try:
        deleted = service.detach_from_allocation(
            actor_id,
            allocation_id,
            security_group_id,
        )
    except (ComputeUnitNotFoundError, SecurityGroupNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Security group attachment was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
