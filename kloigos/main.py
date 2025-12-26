from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import CPU_PORTS_MAP, RANGE_SIZE
from .routers import admin, compute_unit
from .routers.compute_unit import get_compute_units
from .util import cpu_range_to_list

app = FastAPI(
    title="Κλοηγός / Kloigos",
    version="0.2.0",
)

# all API endpoints are grouped in dedicated routers
app.include_router(compute_unit.router)
app.include_router(admin.router)

# needed to serve the static/favicon.png image
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure the templates
templates = Jinja2Templates(directory="kloigos/templates")


# the main app is only configured to serve the Dashboard
@app.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def inventory_dashboard(request: Request):

    # fetch all compute units and dump them into a dict
    inventory = {x.compute_id: x.model_dump() for x in get_compute_units()}

    # enrich the data with the computed cpu_list and ports_range values
    for _, v in inventory.items():
        cpu_list = cpu_range_to_list(v.get("cpu_range"))
        start_port = CPU_PORTS_MAP.get(cpu_list.split(",")[-1])

        v["cpu_list"] = cpu_list
        v["ports_range"] = f"{start_port}-{start_port+RANGE_SIZE}"

    # Prepare the context dictionary to pass data to the HTML template
    context = {
        "request": request,  # Required by Jinja2Templates
        "title": "κλοηγός: Data Center Inventory Dashboard",
        "hosts": inventory,
    }

    # return the HTML page
    return templates.TemplateResponse("dashboard.html", context)
