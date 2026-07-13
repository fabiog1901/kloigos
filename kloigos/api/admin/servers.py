from cpkit import get_audit_actor
from cpkit.jobs.types import JobID
from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...dep import get_admin_service
from ...models import (
    ServerDecommRequest,
    ServerInDB,
    ServerInitRequest,
    ServerNotFoundError,
    ServerStateError,
)
from ...services.admin import AdminService

router = APIRouter(
    prefix="/servers",
    tags=["servers"],
)


@router.get("/", response_model=list[ServerInDB])
async def list_servers(
    hostname: str | None = None,
    service: AdminService = Depends(get_admin_service),
) -> list[ServerInDB]:
    """
    Return physical servers, optionally filtered by hostname.

    Server records describe host-level placement and management details. Use
    `/compute_units/?hostname=<hostname>` to list the compute units hosted on a
    server.
    """
    return service.list_servers(hostname)


@router.post(
    "/",
    summary="Initialize a physical server and its compute units.",
    response_model=JobID,
)
async def init_server(
    sir: ServerInitRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> JobID:
    """
    Register a physical server and schedule bootstrap for its compute units.

    The request body uses explicit compute-unit specs instead of parallel arrays:

    ```json
    {
      "hostname": "s35",
      "private_ip": "10.0.0.10",
      "public_ip": "54.0.0.10",
      "server_admin_user": "ubuntu",
      "region": "us-east-1",
      "zone": "us-east-1a",
      "compute_units": [
        {
          "ordinal": 1,
          "cpu_range": "0-1"
        }
      ]
    }
    ```
    """
    return service.init_server(actor_id, sir)


@router.put("/", response_model=JobID)
async def decommission_server(
    sdr: ServerDecommRequest,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> JobID:
    try:
        return service.decommission_server(actor_id, sdr)
    except ServerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ServerStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{hostname}",
    responses={
        404: {"description": "Server not found."},
        409: {
            "description": "Server is not in a state that can be deleted.",
        },
    },
)
async def delete_server(
    hostname: str,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        service.delete_server(actor_id, hostname)
    except ServerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ServerStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_200_OK)
