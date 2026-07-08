from cpkit import create_cpkit_app, create_cpkit_bundle, template_webapp_directory

from . import DB_URL
from .api import admin, allocation, compute_unit
from .api.admin import license
from .models import (
    AllocationCreateCommand,
    AllocationDeallocateCommand,
    AllocationScaleCommand,
    QueueCommand,
    ServerDecommRequest,
    ServerInitRequest,
)
from .repos import Repo
from .workers.remote import (
    run_allocation_scale,
    run_compute_unit_allocate,
    run_compute_unit_deallocate,
    run_server_decommission,
    run_server_init,
)


cpkit_capabilities = create_cpkit_bundle(
    command_models={
        QueueCommand.ALLOCATION_CREATE: AllocationCreateCommand,
        QueueCommand.ALLOCATION_DELETE: AllocationDeallocateCommand,
        QueueCommand.ALLOCATION_SCALE: AllocationScaleCommand,
        QueueCommand.SERVER_INIT: ServerInitRequest,
        QueueCommand.SERVER_DECOMM: ServerDecommRequest,
    },
    command_handlers={
        QueueCommand.ALLOCATION_CREATE: run_compute_unit_allocate,
        QueueCommand.ALLOCATION_DELETE: run_compute_unit_deallocate,
        QueueCommand.ALLOCATION_SCALE: run_allocation_scale,
        QueueCommand.SERVER_INIT: run_server_init,
        QueueCommand.SERVER_DECOMM: run_server_decommission,
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
        license.router,
    ),
    static_directory=template_webapp_directory(),
    app_static_directory="webapp",
    default_journald_identifier="kloigos",
)
