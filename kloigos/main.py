from cpkit import create_cpkit_app, create_cpkit_bundle, get_repo, template_webapp_directory

from . import DB_URL
from .api import admin, allocation, compute_unit
from .models import AllocationScaleCommand, QueueCommand
from .repos import Repo
from .services.allocation import AllocationService


def run_allocation_scale(job_id: int, payload: AllocationScaleCommand, actor_id: str):
    AllocationService(get_repo()).run_scale_job(job_id, payload, actor_id)

cpkit_capabilities = create_cpkit_bundle(
    command_models={
        QueueCommand.ALLOCATION_SCALE: AllocationScaleCommand,
    },
    command_handlers={
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
