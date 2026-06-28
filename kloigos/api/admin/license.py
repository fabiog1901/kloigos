from cpkit import require_readonly
from fastapi import APIRouter, Depends, Security

from ...dep import get_license_service
from ...models import LicenseStatusResponse
from ...services.admin.license import LicenseService

router = APIRouter(tags=["license"])


@router.get(
    "/license/status",
    response_model=LicenseStatusResponse,
    dependencies=[Security(require_readonly)],
)
async def get_license_status(
    service: LicenseService = Depends(get_license_service),
) -> LicenseStatusResponse:
    """Return the cached enterprise license status."""
    return service.status()
