from fastapi import APIRouter, Depends

from ...dep import get_admin_service
from ...models import LogMsg
from ...services.admin import AdminService

router = APIRouter(
    prefix="/events",
    tags=["events"],
)


@router.get("")
async def list_events(
    service: AdminService = Depends(get_admin_service),
) -> list[LogMsg]:
    return service.list_events()
