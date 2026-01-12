from typing import Callable, Optional

from fastapi import Depends

from .services.admin import AdminService
from .services.compute_unit import ComputeUnitService

# Global references

DB_POOL = None
REPO_FACTORY: Optional[Callable] = None


# 1. The Repo Factory (Hidden from API)
def get_repo():
    if REPO_FACTORY is None:
        raise RuntimeError("Database not initialized. Ensure lifespan ran.")
    return REPO_FACTORY()


# 2. The Service Factory (The only thing API sees)
def get_compute_unit_service(repo=Depends(get_repo)) -> ComputeUnitService:
    return ComputeUnitService(repo)


def get_admin_service(repo=Depends(get_repo)) -> AdminService:
    return AdminService(repo)
