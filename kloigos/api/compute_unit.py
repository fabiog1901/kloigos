from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from ..dep import get_compute_unit_service
from ..models import ComputeUnitRequest, ComputeUnitResponse
from ..services.compute_unit import ComputeUnitService

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
)


@router.post(
    "/allocate",
)
async def allocate(
    req: ComputeUnitRequest,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> ComputeUnitResponse:

    # find and return a free instance that matches the allocate request
    r = service.allocate(req)

    if isinstance(r, int):
        if r == 460:
            raise HTTPException(
                status_code=460,
                detail="No free Compute Unit found to match your request",
            )
        if r == 470:
            raise HTTPException(
                status_code=470,
                detail="Error running allocating playbook",
            )

    return r  # type: ignore


@router.delete(
    "/deallocate/{compute_id}",
)
async def deallocate(
    compute_id: str,
    bg_task: BackgroundTasks,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> Response:

    service.deallocate(compute_id, bg_task)

    # async, run the cleanup task
    # bg_task.add_task(run_deallocate, compute_id)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.get("/")
async def list_servers(
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
