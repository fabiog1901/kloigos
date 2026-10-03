from cpkit import get_audit_actor, require_readonly, require_user
from fastapi import APIRouter, Depends, HTTPException, Response, Security, status

from ..dep import get_ssh_key_service
from ..models import (
    ComputeUnitOperationError,
    SSHKeyCreateRequest,
    SSHKeyCreateResponse,
    SSHKeyInDB,
    SSHKeyNotFoundError,
)
from ..services.ssh_key import SSHKeyService

router = APIRouter(
    prefix="/ssh-keys",
    tags=["ssh-keys"],
)


@router.post(
    "/",
    response_model=SSHKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_user)],
    description=(
        "Create an imported public key or generate a new key pair. This POST is "
        "non-idempotent and clients must not retry it automatically. For generated "
        "keys, the private key is returned only in the initial successful response. "
        "Reusing a key name returns 409 without private-key material. If the outcome "
        "is unknown because the response was lost, inspect the named public-key "
        "resource, delete it if present, and generate a replacement."
    ),
    responses={
        status.HTTP_409_CONFLICT: {
            "description": (
                "The SSH key name already exists; the existing private key is never "
                "returned."
            )
        }
    },
)
async def create_ssh_key(
    req: SSHKeyCreateRequest,
    actor_id: str = Depends(get_audit_actor),
    service: SSHKeyService = Depends(get_ssh_key_service),
) -> SSHKeyCreateResponse:
    """Create an SSH key without supporting automatic retry or response replay."""
    try:
        return service.create_ssh_key(actor_id, req)
    except ComputeUnitOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/",
    response_model=list[SSHKeyInDB],
    dependencies=[Security(require_readonly)],
)
async def list_ssh_keys(
    service: SSHKeyService = Depends(get_ssh_key_service),
) -> list[SSHKeyInDB]:
    """List stored SSH public keys and their metadata."""
    return service.list_ssh_keys()


@router.get(
    "/{name}",
    response_model=SSHKeyInDB,
    dependencies=[Security(require_readonly)],
)
async def get_ssh_key(
    name: str,
    service: SSHKeyService = Depends(get_ssh_key_service),
) -> SSHKeyInDB:
    """Fetch one stored SSH public key by name."""
    try:
        return service.get_ssh_key(name)
    except SSHKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(require_user)],
)
async def delete_ssh_key(
    name: str,
    actor_id: str = Depends(get_audit_actor),
    service: SSHKeyService = Depends(get_ssh_key_service),
) -> Response:
    """Delete one stored SSH key definition."""
    try:
        deleted = service.delete_ssh_key(actor_id, name)
    except SSHKeyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSH key '{name}' was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
