import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from . import DB_ENGINE, DB_URL, dep
from .api import admin, compute_unit
from .enterprise.auth import oidc
from .enterprise.auth import router as auth_router
from .util import RequestIDFilter, ShorthandFormatter, request_id_ctx


def setup_logging():

    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    # Use the Journald Handler or

    if sys.platform == "linux":
        from systemd.journal import JournalHandler

        handler = JournalHandler()
    else:
        # Fallback for environments without systemd-python
        handler = logging.StreamHandler()

    # Add our custom ID filter to the handler
    handler.addFilter(RequestIDFilter())

    # Format: Time | Level | ID | Message
    # Journald also stores metadata fields automatically
    formatter = ShorthandFormatter(
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s"
    )
    formatter.converter = time.gmtime
    formatter.default_msec_format = "%s.%06d"

    handler.setFormatter(formatter)

    logger.addHandler(handler)


setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    oidc.validate_config()

    if DB_ENGINE == "postgres":
        from psycopg_pool import ConnectionPool

        from .repos.postgres import Dict2JsonbDumper, PostgresRepo

        # Initialize the global pool
        dep.DB_POOL = ConnectionPool(
            DB_URL,
            kwargs={"autocommit": True},
            configure=lambda conn: conn.adapters.register_dumper(
                dict, Dict2JsonbDumper
            ),
        )
        dep.REPO_FACTORY = lambda: PostgresRepo(dep.DB_POOL)
    else:
        from .repos.sqlite import SQLiteRepo

        dep.REPO_FACTORY = lambda: SQLiteRepo(DB_URL)

    yield

    # Cleanup
    if dep.DB_POOL:
        dep.DB_POOL.close()


app = FastAPI(lifespan=lifespan)

api = FastAPI(
    title="Κλοηγός / Kloigos",
    version="0.3.0",
)

# all API endpoints are grouped in dedicated routers
api.include_router(auth_router)
api.include_router(compute_unit.router)
api.include_router(admin.router)

app.mount("/api", api)
app.mount(
    "/",
    StaticFiles(directory=Path("webapp"), html=True),
    name="webapp",
)


@app.middleware("http")
async def dispatch(request: Request, call_next):
    # 1. Generate or capture Request ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_ctx.set(request_id)

    start_time = time.perf_counter()

    # 2. Log Incoming
    logging.debug(
        f'<- {request.client[0]}:{request.client[1]} - "{request.method} {request.url.path}"'
    )

    response: Response = await call_next(request)

    # 3. Log Outgoing
    process_time_ms = (time.perf_counter() - start_time) * 1000
    logging.info(
        f'-> {request.client[0]}:{request.client[1]} - "{request.method} {request.url.path}" {response.status_code} | {process_time_ms:.2f}'
    )

    # Return ID to client so they can reference it if they have an error
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = f"{process_time_ms:.2f}"

    return response


# SPA fallback: any non-/api path returns index.html
# @app.get(
#     "/{full_path:path}",
#     include_in_schema=False,
# )
# def webapp_fallback(request: Request, full_path: str):
#     # don't intercept API paths (mounted apps usually handle this, but keep it explicit if needed)
#     if full_path.startswith("api/"):
#         return {"detail": "Not Found"}

#     return FileResponse(WEBAPP / "index.html")
