from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from ...auth import get_audit_actor
from ...dep import get_admin_service
from ...models import (
    DeferredTask,
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


@router.post("/", summary="Initialize a physical server and its compute units.")
async def init_server(
    sir: ServerInitRequest,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    """
    Register a physical server and schedule bootstrap for its compute units.

    The request body uses explicit compute-unit specs instead of parallel arrays:

    ```json
    {
      "hostname": "s35",
      "private_ip": "10.0.0.10",
      "public_ip": "54.0.0.10",
      "user_id": "ubuntu",
      "region": "us-east-1",
      "zone": "us-east-1a",
      "compute_units": [
        {
          "ordinal": 1,
          "cpu_range": "0-1",
          "private_ip": "10.0.0.101",
          "public_ip": "3.0.0.1"
        }
      ]
    }
    ```
    """
    tasks: list[DeferredTask] = service.init_server(actor_id, sir)

    # async, run the init task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


@router.put("/")
async def decommission_server(
    sdr: ServerDecommRequest,
    bg_task: BackgroundTasks,
    actor_id: str = Depends(get_audit_actor),
    service: AdminService = Depends(get_admin_service),
) -> Response:
    tasks: list[DeferredTask] = service.decommission_server(actor_id, sdr)

    # async, run the decomm task
    for t in tasks:
        bg_task.add_task(t.fn, *t.args, **t.kwargs)

    # returns immediately
    return Response(status_code=status.HTTP_200_OK)


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
