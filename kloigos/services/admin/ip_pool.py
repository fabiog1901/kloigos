from cpkit.audit import log_event

from ...models import (
    ComputeUnitOperationError,
    Event,
    IpAddressStatus,
    IpPoolAddressInDB,
    IpPoolInsertRequest,
    IpPoolUpdateRequest,
)
from .base import AdminServiceBase


class IpPoolAdminService(AdminServiceBase):
    def list_ip_pool_addresses(
        self,
        ip_address: str | None = None,
        status: str | None = None,
        allocation_id: str | None = None,
        current_host: str | None = None,
    ) -> list[IpPoolAddressInDB]:
        return self.repo.get_ip_pool_addresses(
            ip_address=ip_address,
            status=status,
            allocation_id=allocation_id,
            current_host=current_host,
        )

    def insert_ip_pool_addresses(
        self,
        actor_id: str,
        req: IpPoolInsertRequest,
    ) -> list[IpPoolAddressInDB]:
        # Floating IPs are durable allocation resources, so admins manage them
        # independently from server/CU initialization.
        requested = set()
        for ip_address in req.ip_addresses:
            if ip_address in requested:
                raise ComputeUnitOperationError(
                    f"IP address {ip_address} is duplicated in the request."
                )
            requested.add(ip_address)

            existing = self.repo.get_ip_pool_addresses(ip_address=ip_address)
            if existing:
                raise ComputeUnitOperationError(
                    f"IP address {ip_address} already exists in the pool."
                )

        for ip_address in req.ip_addresses:
            self.repo.insert_ip_pool_address(
                ip_address=ip_address,
                status=req.status,
                current_host=req.current_host,
            )

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_INSERT,
            req.model_dump(),
        )

        return self.repo.get_ip_pool_addresses()

    def update_ip_pool_address(
        self,
        actor_id: str,
        ip_address: str,
        req: IpPoolUpdateRequest,
    ) -> IpPoolAddressInDB | None:
        self.repo.update_ip_pool_address(
            ip_address=ip_address,
            status=req.status,
            allocation_id=req.allocation_id,
            current_host=req.current_host,
        )

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_UPDATE,
            {
                "ip_address": ip_address,
                **req.model_dump(),
            },
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None

    def delete_ip_pool_address(
        self,
        actor_id: str,
        ip_address: str,
    ) -> bool:
        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        if not matches:
            return False

        existing = matches[0]
        if (
            existing.status != IpAddressStatus.FREE
            or existing.allocation_id is not None
            or existing.current_host is not None
        ):
            raise ComputeUnitOperationError(
                f"IP address {ip_address} must be free and unassigned before removal."
            )

        deleted = self.repo.delete_ip_pool_address(ip_address)
        if deleted:
            log_event(
                self.repo,
                actor_id,
                Event.IP_POOL_DELETE,
                existing.model_dump(),
            )
        return deleted

    def release_ip_pool_address(
        self,
        actor_id: str,
        allocation_id: str,
    ) -> IpPoolAddressInDB | None:
        matches = self.repo.get_ip_pool_addresses(allocation_id=allocation_id)
        if not matches:
            return None

        ip_address = matches[0].ip_address
        self.repo.release_ip_pool_address(
            ip_address=ip_address,
            status=IpAddressStatus.FREE,
        )

        log_event(
            self.repo,
            actor_id,
            Event.IP_POOL_RELEASE,
            {
                "allocation_id": allocation_id,
                "ip_address": ip_address,
            },
        )

        matches = self.repo.get_ip_pool_addresses(ip_address=ip_address)
        return matches[0] if matches else None
