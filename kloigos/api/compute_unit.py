from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    Security,
    status,
)
from fastapi.exceptions import RequestErrorModel

from ..auth import get_audit_actor, require_compute_access
from ..dep import get_compute_unit_service
from ..models import (
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    ComputeUnitOverview,
    ComputeUnitRequest,
    ComputeUnitStateError,
    DeferredTask,
    NoFreeComputeUnitError,
)
from ..services.compute_unit import ComputeUnitService

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
    dependencies=[Security(require_compute_access)],
)


@router.post(
    "/allocate",
    summary="Allocate a Compute Unit.",
    response_model=str,
    responses={
        460: {
            "model": RequestErrorModel,
            "description": "No free compute unit found to match the request",
        },
        500: {
            "model": RequestErrorModel,
            "description": "The compute unit was reserved but the allocation request could not be prepared",
        },
    },
)
async def allocate(
    req: ComputeUnitRequest,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> str:
    """
    Reserve a free compute unit and schedule the background allocation playbook.

    The endpoint returns quickly once the unit is reserved. The slower machine
    preparation work continues in the background.
    """
    try:
        compute_id, tasks = service.allocate(actor_id, req)

        for t in tasks:
            bg_task.add_task(t.fn, *t.args, **t.kwargs)

        return compute_id
    except NoFreeComputeUnitError:
        raise HTTPException(460, "No free Compute Unit found to match your request")
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/deallocate/{compute_id}",
    summary="Deallocate a Compute Unit.",
    responses={
        404: {
            "model": RequestErrorModel,
            "description": "The requested compute unit does not exist",
        },
        409: {
            "model": RequestErrorModel,
            "description": "The compute unit is in a state that cannot be deallocated",
        },
        500: {
            "model": RequestErrorModel,
            "description": "The deallocation request could not be prepared",
        },
    },
)
async def deallocate(
    compute_id: str,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> Response:
    """
    Mark a compute unit for deallocation and schedule the cleanup playbook.

    The endpoint validates that the unit exists and is in a state where cleanup
    makes sense before queueing the background job.
    """
    try:
        tasks: list[DeferredTask] = service.deallocate(actor_id, compute_id)
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

    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.get("/")
async def list_compute_units(
    compute_id: str | None = None,
    hostname: str | None = None,
    region: str | None = None,
    zone: str | None = None,
    cpu_count: int | None = None,
    deployment_id: str | None = None,
    status: str | None = None,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> list[ComputeUnitOverview]:
    """
    Return compute units, optionally filtered by id, host, region, size, tags, or status.

    Example:
    - /compute_units
    - /compute_units?deployment_id=web_app_v1
    - /compute_units?status=FREE
    """

    return service.list_compute_units(
        compute_id,
        hostname,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )
