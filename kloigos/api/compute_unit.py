from cpkit import require_readonly
from fastapi import APIRouter, Depends, Security

from ..dep import get_compute_unit_service
from ..models import ComputeUnitOverview
from ..services.compute_unit import ComputeUnitService

router = APIRouter(
    prefix="/compute_units",
    tags=["compute_units"],
    dependencies=[Security(require_readonly)],
)


@router.get("/", response_model=list[ComputeUnitOverview])
async def list_compute_units(
    compute_id: str | None = None,
    hostname: str | None = None,
    region: str | None = None,
    zone: str | None = None,
    cpu_count: int | None = None,
    deployment_id: str | None = None,
    status: str | None = None,
    service: ComputeUnitService = Depends(get_compute_unit_service),
) -> list[ComputeUnitOverview]:
    """
    Return compute units, optionally filtered by id, host, region, size, tags, or status.

    Each compute unit includes its deterministic `compute_id`, parent `hostname`,
    internal `private_ip`, optional external `public_ip`, and the parent server's
    management IPs.

    Example:
    - /compute_units
    - /compute_units?deployment_id=web_app_v1
    - /compute_units?status=FREE
    """

    return service.list_compute_units(
        compute_id,
        hostname,
        region,
        zone,
        cpu_count,
        deployment_id,
        status,
    )
