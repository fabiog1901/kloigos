from cpkit import get_repo
from fastapi import Depends

from .services.allocation import AllocationService
from .services.admin import AdminService
from .services.compute_unit import ComputeUnitService


def get_allocation_service(repo=Depends(get_repo)) -> AllocationService:
    return AllocationService(repo)


def get_compute_unit_service(repo=Depends(get_repo)) -> ComputeUnitService:
    return ComputeUnitService(repo)


def get_admin_service(repo=Depends(get_repo)) -> AdminService:
    return AdminService(repo)
