from cpkit import require_admin
from fastapi import APIRouter, Security

from . import servers

router = APIRouter(
    prefix="/admin",
    dependencies=[Security(require_admin)],
)

router.include_router(servers.router)
