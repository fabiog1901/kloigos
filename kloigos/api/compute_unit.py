from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestErrorModel

from ..dep import get_compute_unit_service
from ..models import ComputeUnitOverview, ComputeUnitRequest, DeferredTask
from ..services.compute_unit import ComputeUnitService, NoFreeComputeUnitError

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
)


@router.post(
    "/allocate",
    summary="Allocate a Compute Unit.",
    response_model=str,
    responses={
        460: {
            "model": RequestErrorModel,
            "description": "No free Compute Unit found to match the request",
        },
    },
)
async def allocate(
    req: ComputeUnitRequest,
    bg_task: BackgroundTasks,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> str:

    # find and return a free instance that matches the allocate request
    try:
        compute_id, tasks = service.allocate(req)

        for t in tasks:
            bg_task.add_task(t.fn, *t.args, **t.kwargs)

        return compute_id
    except NoFreeComputeUnitError:
        raise HTTPException(460, "No free Compute Unit found to match your request")


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
) -> list[ComputeUnitOverview]:
    """
    Returns a list of all servers.
    Optionally filter the results by 'deployment_id' or 'status' query parameters.

    Example:
    - /servers
    - /servers?deployment_id=web_app_v1
    - /servers?status=free
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
