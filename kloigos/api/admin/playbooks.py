from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status

from ...auth import get_audit_actor
from ...dep import get_admin_service
from ...models import Playbook
from ...services.admin import AdminService

router = APIRouter(
    prefix="/playbooks",
    tags=["playbooks"],
)


@router.patch("/{playbook}")
async def update_playbook(
    playbook: Playbook,
    # Annotated tells FastAPI this MUST come from the Body
    b64: Annotated[str, Body(description="The base64 encoded string")],
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    service.update_playbooks(actor_id, playbook, b64)
    return Response(status_code=status.HTTP_200_OK)


@router.get("/{playbook}")
async def get_playbook(
    playbook: Playbook,
    service: AdminService = Depends(get_admin_service),
) -> str:
    return service.get_playbook(playbook)
