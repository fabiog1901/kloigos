from cpkit import create_cpkit_app, create_cpkit_bundle

from . import DB_URL
from .api import admin, compute_unit
from .repos import Repo

cpkit_capabilities = create_cpkit_bundle(
    parse_job_payload=lambda _job_type, payload: payload or {},
)

app = create_cpkit_app(
    title="Κλοηγός / Kloigos",
    version="0.4.0",
    repo_class=Repo,
    db_url=DB_URL,
    capabilities=(cpkit_capabilities,),
    routers=(
        admin.router,
        compute_unit.router,
    ),
    static_directory="webapp",
    default_journald_identifier="kloigos",
)
