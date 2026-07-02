from cpkit import get_audit_actor
from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...dep import get_admin_service
from ...models import (
    ComputeUnitOperationError,
    IpPoolAddressInDB,
    IpPoolInsertRequest,
)
from ...services.admin import AdminService

router = APIRouter(
    prefix="/ip_pool",
    tags=["ip_pool"],
)


@router.get("/", response_model=list[IpPoolAddressInDB])
async def list_ip_pool_addresses(
    ip_address: str | None = None,
    status: str | None = None,
    allocation_id: str | None = None,
    current_host: str | None = None,
    service: AdminService = Depends(get_admin_service),
) -> list[IpPoolAddressInDB]:
    return service.list_ip_pool_addresses(
        ip_address=ip_address,
        status=status,
        allocation_id=allocation_id,
        current_host=current_host,
    )


@router.post("/", response_model=list[IpPoolAddressInDB])
async def insert_ip_pool_addresses(
    req: IpPoolInsertRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> list[IpPoolAddressInDB]:
    try:
        return service.insert_ip_pool_addresses(actor_id, req)
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete("/{ip_address}")
async def delete_ip_pool_address(
    ip_address: str,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        deleted = service.delete_ip_pool_address(actor_id, ip_address)
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP address {ip_address} was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
