import datetime as dt
import sys
import threading
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Κλοηγός")

INVENTORY_FILE = "inventory.yaml"
RANGE_SIZE=200
CPU_PORTS_MAP = {f"{k}": 2000 + i * RANGE_SIZE for i, k in enumerate(range(256))}

# Use a lock to prevent race conditions when multiple Ansible playbooks
# try to allocate hosts at the exact same time.
inventory_lock = threading.Lock()


class HostDetails(BaseModel):
    ansible_host: str
    hostname: str
    ip: str
    cpu_range: str
    ports_range: str | None
    status: str
    started_at: dt.datetime | None
    tags: dict[str, Any] | None
    labels: list[str] | None


class ProvisionRequest(BaseModel):
    name: str


class DeprovisionRequest(BaseModel):
    hostname: str


@app.post(
    "/provision",
)
async def provision_resources(
    pr: ProvisionRequest,
) -> HostDetails:

    result = manage_inventory_file("provision", pr.name)

    if isinstance(result, HostDetails):
        return result

    raise HTTPException(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="no host available"
    )


@app.post(
    "/deprovision",
)
async def deprovision_resources(
    dr: DeprovisionRequest,
):

    result = manage_inventory_file("deprovision", dr.hostname)

    if result == "OK":
        return

    raise HTTPException(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=result
    )


@app.get("/servers")
async def list_servers(
    deployment_id: str | None = None,
    status: str | None = None,
) -> list[HostDetails]:
    """
    Returns a list of all servers.
    Optionally filter the results by 'deployment_id' or 'status' query parameters.

    Example:
    - /servers
    - /servers?deployment_id=web_app_v1
    - /servers?status=free
    """

    filtered_hosts = []
    inventory_raw = {}

    with open(INVENTORY_FILE, "r") as f:
        inventory_raw: dict[str, dict] = yaml.safe_load(f)

        inventory: list[HostDetails] = []
        for k, v in inventory_raw.items():
            s = CPU_PORTS_MAP[v.get("cpu_range").split(",")[-1]]
            ports_range = f"{s}-{s + RANGE_SIZE}"
            inventory.append(HostDetails(ansible_host=k, ports_range=ports_range, **v))

    for x in inventory:

        # Check deployment_id filter (if provided)
        deployment_id_match = (deployment_id is None) or (
            x.tags.get("deployment_id", "") == deployment_id
        )

        # Check status filter (if provided)
        status_match = (status is None) or (x.status == status)

        # If both matches are true, include the host
        if deployment_id_match and status_match:
            # We explicitly create the AllocatedHost Pydantic object
            filtered_hosts.append(x)

    return filtered_hosts


def manage_inventory_file(action: str, item: str):

    with inventory_lock:
        try:
            # 1. Load Inventory
            with open(INVENTORY_FILE, "r") as f:
                inventory_raw: dict[str, dict] = yaml.safe_load(f)
        except FileNotFoundError:
            print(
                f"Error: Inventory file '{INVENTORY_FILE}' not found.", file=sys.stderr
            )
            return {"status": "error", "message": f"Inventory file missing."}

        inventory: list[HostDetails] = [
            HostDetails(ansible_host=k, **v) for k, v in inventory_raw.items()
        ]

        if action == "provision":
            # Find the first free host
            available_host_name = None
            for h in inventory:
                if h.status == "free":
                    available_host_name = h

                    h.status = "running"
                    h.deployment_id = item

                    with open(INVENTORY_FILE, "w") as f:
                        yaml.dump(
                            [x.model_dump() for x in inventory],
                            f,
                            default_flow_style=False,
                        )

                    return available_host_name

            return {"status": "error", "message": "No free hosts available"}

        elif action == "deprovision":
            for h in inventory:
                if h.hostname == item:

                    h.status = "free"
                    h.deployment_id = None

                    with open(INVENTORY_FILE, "w") as f:
                        yaml.dump(
                            [x.model_dump() for x in inventory],
                            f,
                            default_flow_style=False,
                        )

                    return "OK"

            return "Host not found"


# Configure the templates
templates = Jinja2Templates(directory="kloigos/templates")


@app.get("/", response_class=HTMLResponse)
async def inventory_dashboard(request: Request):

    # 1. Load the current inventory data from the YAML file
    with open(INVENTORY_FILE, "r") as f:
        inventory = yaml.safe_load(f)

    # 2. Prepare the context dictionary to pass data to the HTML template
    context = {
        "request": request,  # Required by Jinja2Templates
        "title": "κλοηγός: Data Center Inventory Dashboard",
        "hosts": inventory,
        "cpu_ports_map": CPU_PORTS_MAP,
        "range_size": RANGE_SIZE,
    }

    # 3. Render the HTML page
    return templates.TemplateResponse("dashboard.html", context)
