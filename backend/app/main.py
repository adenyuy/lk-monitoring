"""Server lokal: API di /api, tampilan Next.js (static export) di /."""

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from . import chat_refresh, config, db, paths
from .routers import chat, core, cutoff, lk, rekap, send, today, wa
from .wa.browser import worker


def _setup_logging() -> None:
    paths.ensure_dirs()
    handler = RotatingFileHandler(paths.LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


_setup_logging()
db.connect()

@asynccontextmanager
async def lifespan(_: FastAPI):
    chat_refresh.start_background()
    yield
    worker.shutdown()  # tutup Chrome WhatsApp dengan rapi


app = FastAPI(
    title="LK Monitoring",
    version=config.VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Hanya untuk `next dev` di port 3000. Di produksi web & API satu origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.DEV_WEB_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core.router)
app.include_router(wa.router)
app.include_router(send.router)
app.include_router(today.router)
app.include_router(lk.router)
app.include_router(chat.router)
app.include_router(rekap.router)
app.include_router(cutoff.router)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(rest: str) -> None:
    raise HTTPException(404, f"Endpoint /api/{rest} tidak ada.")


# ---------- tampilan (web/out) ----------

def _resolve_static(path: str) -> Path | None:
    """'/today/' -> out/today/index.html; '/_next/x.js' -> out/_next/x.js. Cegah keluar folder."""
    out = paths.WEB_OUT_DIR.resolve()
    target = (out / path.lstrip("/")).resolve()
    if out not in target.parents and target != out:
        return None
    for candidate in (target, target / "index.html", target.with_suffix(".html")):
        if candidate.is_file():
            return candidate
    return None


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def web(path: str):
    if not paths.WEB_OUT_DIR.exists():
        return HTMLResponse(
            "<h1>Tampilan belum dibangun</h1><p>Jalankan <code>npm run build</code> di folder web, "
            "atau pakai scripts/dev.bat saat develop.</p>",
            status_code=503,
        )
    found = _resolve_static(path)
    if found:
        return FileResponse(found)
    not_found = paths.WEB_OUT_DIR / "404.html"
    return FileResponse(not_found, status_code=404) if not_found.exists() else HTMLResponse("Tidak ditemukan", 404)
