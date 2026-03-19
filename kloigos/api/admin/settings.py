from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestErrorModel

from ...auth import get_audit_actor
from ...dep import get_admin_service
from ...models import (
    SettingKey,
    SettingNotFoundError,
    SettingRecord,
    SettingUpdateRequest,
)
from ...services.admin import AdminService

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


@router.get("/")
async def list_settings(
    service: AdminService = Depends(get_admin_service),
) -> list[SettingRecord]:
    return service.list_settings()


@router.get(
    "/{key}",
    responses={
        404: {
            "model": RequestErrorModel,
            "description": "Setting not found.",
        },
    },
)
async def get_setting(
    key: SettingKey,
    service: AdminService = Depends(get_admin_service),
) -> SettingRecord:
    try:
        return service.get_setting(key)
    except SettingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found.",
        )


@router.patch(
    "/{key}",
    responses={
        404: {
            "model": RequestErrorModel,
            "description": "Setting not found.",
        },
    },
)
async def update_setting(
    key: SettingKey,
    request: SettingUpdateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> SettingRecord:
    try:
        return service.update_setting(actor_id, key, request.value)
    except SettingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found.",
        )


@router.put(
    "/{key}",
    responses={
        404: {
            "model": RequestErrorModel,
            "description": "Setting not found.",
        },
    },
)
async def reset_setting(
    key: SettingKey,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> SettingRecord:
    try:
        return service.reset_setting(actor_id, key)
    except SettingNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found.",
        )
