from fastapi import APIRouter, Security

from ...auth import require_admin
from . import api_keys, events, playbooks, servers, settings

router = APIRouter(
    prefix="/admin",
    dependencies=[Security(require_admin)],
)

router.include_router(playbooks.router)
router.include_router(servers.router)
router.include_router(events.router)
router.include_router(api_keys.router)
router.include_router(settings.router)
