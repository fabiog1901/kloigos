import datetime as dt
import sys
import threading
from typing import Literal

import yaml
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

app = FastAPI()

INVENTORY_FILE = "inventory.yaml"


# Use a lock to prevent race conditions when multiple Ansible playbooks
# try to allocate hosts at the exact same time.
inventory_lock = threading.Lock()


class HostDetails(BaseModel):
    hostname: str
    ansible_host: str
    numa_node: int
    service_name: str | None
    started_at: dt.datetime | None
    owner: str | None
    status: str


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
    service_name: str | None = None,
    status: str | None = None,
) -> list[HostDetails]:
    """
    Returns a list of all servers.
    Optionally filter the results by 'service_name' or 'status' query parameters.

    Example:
    - /servers
    - /servers?service_name=web_app_v1
    - /servers?status=free
    """

    filtered_hosts = []
    inventory_dict = {}

    with open(INVENTORY_FILE, "r") as f:
        inventory_dict = yaml.safe_load(f)

    inventory: list[HostDetails] = [HostDetails(**x) for x in inventory_dict]

    for h in inventory:

        # Check service_name filter (if provided)
        service_match = (service_name is None) or (h.service_name == service_name)

        # Check status filter (if provided)
        status_match = (status is None) or (h.status == status)

        # If both matches are true, include the host
        if service_match and status_match:
            # We explicitly create the AllocatedHost Pydantic object
            filtered_hosts.append(h)

    return filtered_hosts


def manage_inventory_file(action: str, item: str):

    with inventory_lock:
        try:
            # 1. Load Inventory
            with open(INVENTORY_FILE, "r") as f:
                inventory_raw = yaml.safe_load(f)
        except FileNotFoundError:
            print(
                f"Error: Inventory file '{INVENTORY_FILE}' not found.", file=sys.stderr
            )
            return {"status": "error", "message": f"Inventory file missing."}

        inventory: list[HostDetails] = [HostDetails(**x) for x in inventory_raw]

        if action == "provision":
            # Find the first free host
            available_host_name = None
            for h in inventory:
                if h.status == "free":
                    available_host_name = h

                    h.status = "running"
                    h.service_name = item

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
                    h.service_name = None

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
        inventory: list[dict[str, any]] = yaml.safe_load(f)

    inventory_data = inventory

    # 2. Prepare the context dictionary to pass data to the HTML template
    context = {
        "request": request,  # Required by Jinja2Templates
        "title": "κλοηγός: Data Center Inventory Dashboard",
        "hosts": inventory_data,
    }

    # 3. Render the HTML page
    return templates.TemplateResponse("dashboard.html", context)
