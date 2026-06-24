from cpkit import create_cpkit_app, create_cpkit_bundle, template_webapp_directory

from . import DB_URL
from .api import admin, allocation, compute_unit
from .models import AllocationCreateCommand, AllocationScaleCommand, QueueCommand
from .repos import Repo
from .workers.remote import run_allocation_scale, run_compute_unit_allocate

cpkit_capabilities = create_cpkit_bundle(
    command_models={
        QueueCommand.CU_ALLOCATE: AllocationCreateCommand,
        QueueCommand.ALLOCATION_SCALE: AllocationScaleCommand,
    },
    command_handlers={
        QueueCommand.CU_ALLOCATE: run_compute_unit_allocate,
        QueueCommand.ALLOCATION_SCALE: run_allocation_scale,
    },
)

app = create_cpkit_app(
    title="Κλοηγός / Kloigos",
    version="0.4.0",
    repo_class=Repo,
    db_url=DB_URL,
    capabilities=(cpkit_capabilities,),
    routers=(
        admin.router,
        allocation.router,
        compute_unit.router,
    ),
    static_directory=template_webapp_directory(),
    app_static_directory="webapp",
    default_journald_identifier="kloigos",
)
