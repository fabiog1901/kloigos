from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Response, status

from ..dep import get_admin_service
from ..models import DeferredTask, InitServerRequest, Playbook
from ..services.admin import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
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


@router.post(
    "/init_server",
)
async def init_server(
    isr: InitServerRequest,
    bg_task: BackgroundTasks,
    service: AdminService = Depends(get_admin_service),
) -> Response:

    # add the server to the compute_units table with
    # status='init'
    tasks: list[DeferredTask] = service.init_server(isr)

    # async, run the init task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.delete(
    "/decommission_server/{hostname}",
)
async def decommission_server(
    hostname: str,
    bg_task: BackgroundTasks,
    service: AdminService = Depends(get_admin_service),
) -> Response:

    tasks: list[DeferredTask] = service.decommission_server(hostname)

    # async, run the decomm task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)
