from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Response,
    Security,
    status,
)

from ..dep import get_admin_service
from ..enterprise.auth import require_authenticated
from ..models import (
    DeferredTask,
    Playbook,
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
)
from ..services.admin import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Security(require_authenticated)],
)


@router.patch("/playbooks/{playbook}")
async def update_playbook(
    playbook: Playbook,
    # Annotated tells FastAPI this MUST come from the Body
    b64: Annotated[str, Body(description="The base64 encoded string")],
    service: AdminService = Depends(get_admin_service),
):

    service.update_playbooks(playbook, b64)

    return Response(status_code=status.HTTP_200_OK)


@router.get("/playbooks/{playbook}")
async def get_playbook(
    playbook: Playbook,
    service: AdminService = Depends(get_admin_service),
) -> str:

    return service.get_playbook(playbook)


@router.get(
    "/servers/",
)
async def list_servers(
    hostname: str | None = None,
    service: AdminService = Depends(get_admin_service),
) -> list[ServerInDB]:

    return service.list_servers(hostname)


@router.post(
    "/servers/",
)
async def init_server(
    sir: ServerInitRequest,
    bg_task: BackgroundTasks,
    service: AdminService = Depends(get_admin_service),
) -> Response:

    # add the server to the compute_units table with
    # status='init'
    tasks: list[DeferredTask] = service.init_server(sir)

    # async, run the init task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.put(
    "/servers/",
)
async def decommission_server(
    sdr: ServerDecommRequest,
    bg_task: BackgroundTasks,
    service: AdminService = Depends(get_admin_service),
) -> Response:

    tasks: list[DeferredTask] = service.decommission_server(sdr)

    # async, run the decomm task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.delete(
    "/servers/{hostname}",
)
async def delete_server(
    hostname: str,
    service: AdminService = Depends(get_admin_service),
) -> Response:
    service.delete_server(hostname)

    return Response(status_code=status.HTTP_200_OK)
