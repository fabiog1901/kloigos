from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from ...auth import get_audit_actor
from ...dep import get_admin_service
from ...models import DeferredTask, ServerDecommRequest, ServerInDB, ServerInitRequest
from ...services.admin import AdminService

router = APIRouter(
    prefix="/servers",
    tags=["servers"],
)


@router.get("/")
async def list_servers(
    hostname: str | None = None,
    service: AdminService = Depends(get_admin_service),
) -> list[ServerInDB]:
    return service.list_servers(hostname)


@router.post("/")
async def init_server(
    sir: ServerInitRequest,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    # add the server to the compute_units table with status='init'
    tasks: list[DeferredTask] = service.init_server(actor_id, sir)

    # async, run the init task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.put("/")
async def decommission_server(
    sdr: ServerDecommRequest,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    tasks: list[DeferredTask] = service.decommission_server(actor_id, sdr)

    # async, run the decomm task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.delete("/{hostname}")
async def delete_server(
    hostname: str,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    service.delete_server(actor_id, hostname)
    return Response(status_code=status.HTTP_200_OK)
