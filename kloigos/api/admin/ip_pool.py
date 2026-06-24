from cpkit import get_audit_actor
from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...dep import get_admin_service
from ...models import IpPoolAddressInDB, IpPoolUpdateRequest, IpPoolUpsertRequest
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
async def upsert_ip_pool_addresses(
    req: IpPoolUpsertRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> list[IpPoolAddressInDB]:
    return service.upsert_ip_pool_addresses(actor_id, req)


@router.put("/{ip_address}", response_model=IpPoolAddressInDB)
async def update_ip_pool_address(
    ip_address: str,
    req: IpPoolUpdateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> IpPoolAddressInDB:
    updated = service.update_ip_pool_address(actor_id, ip_address, req)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IP address {ip_address} was not found.",
        )
    return updated


@router.delete("/{allocation_id}")
async def release_ip_pool_address(
    allocation_id: str,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    released = service.release_ip_pool_address(actor_id, allocation_id)
    if not released:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation {allocation_id} has no assigned IP address.",
        )
    return Response(status_code=status.HTTP_200_OK)
