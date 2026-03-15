from fastapi import APIRouter, Security

from ...auth import require_admin
from . import events, playbooks, servers

router = APIRouter(
    prefix="/admin",
    dependencies=[Security(require_admin)],
)

router.include_router(playbooks.router)
router.include_router(servers.router)
router.include_router(events.router)
