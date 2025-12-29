from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import admin, compute_unit

app = FastAPI()
api = FastAPI(
    title="Κλοηγός / Kloigos",
    version="0.2.0",
)

# all API endpoints are grouped in dedicated routers
api.include_router(compute_unit.router)
api.include_router(admin.router)

WEBAPP = Path("webapp")  # e.g. Vite build output

app.mount("/api", api)
app.mount("/static", StaticFiles(directory=WEBAPP / "static"), name="static")


# SPA fallback: any non-/api path returns index.html
@app.get(
    "/{full_path:path}",
    include_in_schema=False,
)
def webapp_fallback(request: Request, full_path: str):
    # don't intercept API paths (mounted apps usually handle this, but keep it explicit if needed)
    if full_path.startswith("api/"):
        return {"detail": "Not Found"}

    return FileResponse(WEBAPP / "index.html")
