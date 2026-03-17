from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...auth import get_audit_actor
from ...dep import get_admin_service
from ...models import (
    ApiKeyAlreadyExistsError,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyNotFoundError,
    ApiKeySummary,
    InvalidApiKeyValidityError,
)
from ...services.admin import AdminService
from fastapi.exceptions import RequestErrorModel

router = APIRouter(
    prefix="/api_keys",
    tags=["api_keys"],
)


@router.get("/")
async def list_api_keys(
    access_key: str | None = None,
    service: AdminService = Depends(get_admin_service),
) -> list[ApiKeySummary]:
    return service.list_api_keys(access_key)


@router.post(
    "/",
    response_model=ApiKeyCreateResponse,
    responses={
        400: {
            "model": RequestErrorModel,
            "description": "valid_until must be in the future.",
        },
        409: {
            "model": RequestErrorModel,
            "description": "API key already exists.",
        },
    },
)
async def create_api_key(
    request: ApiKeyCreateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> ApiKeyCreateResponse:
    try:
        return service.create_api_key(actor_id, request)
    except InvalidApiKeyValidityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="valid_until must be in the future.",
        )
    except ApiKeyAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key already exists.",
        )


@router.delete(
    "/{access_key}",
    responses={
        404: {
            "model": RequestErrorModel,
            "description": "API key not found.",
        },
    },
)
async def delete_api_key(
    access_key: str,
    service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        service.delete_api_key(access_key)
    except ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )
    return Response(status_code=status.HTTP_200_OK)
