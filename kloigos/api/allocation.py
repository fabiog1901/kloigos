from cpkit import get_audit_actor, require_readonly, require_user
from cpkit.jobs.types import JobID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Security,
    status,
)

from ..dep import get_allocation_service
from ..models import (
    AllocationInDB,
    AllocationCreateResponse,
    AllocationScaleRequest,
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitRequest,
    ComputeUnitStateError,
    NoFreeComputeUnitError,
    NoFreeIpAddressError,
)
from ..services.allocation import AllocationService

router = APIRouter(
    prefix="/allocations",
    tags=["allocations"],
)


@router.get(
    "/",
    response_model=list[AllocationInDB],
    dependencies=[Security(require_readonly)],
)
async def list_allocations(
    allocation_id: str | None = None,
    compute_id: str | None = None,
    ip_address: str | None = None,
    status: str | None = None,
    service: AllocationService = Depends(get_allocation_service),
) -> list[AllocationInDB]:
    """List allocations with floating IP and current login user, optionally filtered."""
    return service.list_allocations(
        allocation_id=allocation_id,
        compute_id=compute_id,
        ip_address=ip_address,
        status=status,
    )


@router.post(
    "/",
    response_model=AllocationCreateResponse,
    dependencies=[Security(require_user)],
)
async def allocate(
    req: ComputeUnitRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AllocationService = Depends(get_allocation_service),
) -> AllocationCreateResponse:
    """Create an allocation and queue compute-unit setup as a cpkit job."""
    try:
        return service.allocate(actor_id, req)
    except NoFreeComputeUnitError:
        raise HTTPException(460, "No free Compute Unit found to match your request")
    except NoFreeIpAddressError:
        raise HTTPException(460, "No free IP address found to match your request")
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/{allocation_id}",
    response_model=AllocationInDB,
    dependencies=[Security(require_readonly)],
)
async def get_allocation(
    allocation_id: str,
    service: AllocationService = Depends(get_allocation_service),
) -> AllocationInDB:
    """Fetch one allocation by durable allocation id, including current login user."""
    try:
        return service.get_allocation(allocation_id)
    except ComputeUnitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{allocation_id}",
    response_model=JobID,
    dependencies=[Security(require_user)],
)
async def deallocate_allocation(
    allocation_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: AllocationService = Depends(get_allocation_service),
) -> JobID:
    """Queue a cpkit job to deallocate the compute unit backing an allocation."""
    try:
        return service.deallocate(actor_id, allocation_id)
    except ComputeUnitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ComputeUnitStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post(
    "/{allocation_id}/scale",
    response_model=JobID,
    dependencies=[Security(require_user)],
)
async def scale_allocation(
    allocation_id: str,
    req: AllocationScaleRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AllocationService = Depends(get_allocation_service),
) -> JobID:
    """Queue a cpkit job to scale an allocation onto another compute unit."""
    try:
        return service.scale(actor_id, allocation_id, req)
    except ComputeUnitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
