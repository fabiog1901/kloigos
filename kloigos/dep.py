from cpkit import get_repo
from fastapi import Depends

from .services.admin import AdminService
from .services.allocation import AllocationService
from .services.compute_unit import ComputeUnitService
from .services.security_group import SecurityGroupService


def get_allocation_service(repo=Depends(get_repo)) -> AllocationService:
    return AllocationService(repo)


def get_compute_unit_service(repo=Depends(get_repo)) -> ComputeUnitService:
    return ComputeUnitService(repo)


def get_admin_service(repo=Depends(get_repo)) -> AdminService:
    return AdminService(repo)


def get_security_group_service(repo=Depends(get_repo)) -> SecurityGroupService:
    return SecurityGroupService(repo)
