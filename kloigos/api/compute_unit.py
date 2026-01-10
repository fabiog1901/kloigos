from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestErrorModel

from ..dep import get_compute_unit_service
from ..models import ComputeUnitRequest, ComputeUnitResponse, DeferredTask
from ..services.compute_unit import (
    AllocatePlaybookError,
    ComputeUnitService,
    NoFreeComputeUnitError,
)

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
)


@router.post(
    "/allocate",
    summary="Allocate a Compute Unit.",
    response_model=ComputeUnitResponse,
    responses={
        460: {
            "model": RequestErrorModel,
            "description": "No free Compute Unit found to match the request",
        },
        470: {
            "model": RequestErrorModel,
            "description": "Error running allocating playbook",
        },
    },
)
async def allocate(
    req: ComputeUnitRequest,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> ComputeUnitResponse:

    # find and return a free instance that matches the allocate request
    try:
        return service.allocate(req)
    except NoFreeComputeUnitError:
        raise HTTPException(460, "No free Compute Unit found to match your request")
    except AllocatePlaybookError:
        raise HTTPException(470, "Error running allocating playbook")


@router.delete(
    "/deallocate/{compute_id}",
    summary="Deallocate a Compute Unit.",
)
async def deallocate(
    compute_id: str,
    bg_task: BackgroundTasks,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> Response:

    tasks: list[DeferredTask] = service.deallocate(compute_id)

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
) -> list[ComputeUnitResponse]:
    """
    Returns a list of all servers.
    Optionally filter the results by 'deployment_id' or 'status' query parameters.

    Example:
    - /servers
    - /servers?deployment_id=web_app_v1
    - /servers?status=free
    """

    return service.list_server(
        compute_id,
        hostname,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )
