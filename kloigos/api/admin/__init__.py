from cpkit import require_admin
from fastapi import APIRouter, Security

from . import ip_pool, servers

router = APIRouter(
    prefix="/admin",
    dependencies=[Security(require_admin)],
)

router.include_router(servers.router)
router.include_router(ip_pool.router)
