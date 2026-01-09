from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import DB_ENGINE, DB_URL, dep
from .api import admin, compute_unit


@asynccontextmanager
async def lifespan(_app: FastAPI):
    print(f"Initializing {DB_ENGINE}...")

    if DB_ENGINE == "postgres":
        from psycopg_pool import ConnectionPool

        from .repos.postgres import PostgresRepo

        # Initialize the global pool
        dep.db_pool = ConnectionPool(DB_URL)
        dep.repo_factory = lambda: PostgresRepo(dep.db_pool)
    else:
        from .repos.sqlite import SQLiteRepo

        dep.repo_factory = lambda: SQLiteRepo("local.db")

    yield

    # Cleanup
    if dep.db_pool:
        dep.db_pool.close()


app = FastAPI(lifespan=lifespan)

api = FastAPI(
    title="Κλοηγός / Kloigos",
    version="0.2.0",
)

# all API endpoints are grouped in dedicated routers
api.include_router(compute_unit.router)
api.include_router(admin.router)

app.mount("/api", api)
app.mount(
    "/",
    StaticFiles(directory=Path("webapp"), html=True),
    name="webapp",
)


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
