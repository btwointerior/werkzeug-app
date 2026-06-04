"""FastAPI-App für die Werkzeug-Ausleihe."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.auth import create_access_token, decode_access_token
from backend.config import settings
from backend.models import init_db
from backend.routers import admin_router, auth_router, maschinen_router
from backend import uploads_router

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_INDEX_HTML = _FRONTEND_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Werkzeug-Ausleihe API",
    description=(
        "REST-API für die interne Werkzeug-/Maschinen-Ausleihe bei "
        "bühler² interior."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-New-Token"],
)


@app.middleware("http")
async def sliding_token_middleware(request: Request, call_next):
    """Verlängert bei jedem erfolgreichen authentifizierten Request den Token.

    Der neue Token wird im Response-Header `X-New-Token` zurückgegeben. Der
    Client soll diesen Header auslesen und seinen gespeicherten Token ersetzen.
    """
    response = await call_next(request)
    if response.status_code < 400:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            benutzer_id = decode_access_token(token)
            if benutzer_id is not None:
                response.headers["X-New-Token"] = create_access_token(benutzer_id)
    return response


app.include_router(auth_router.router)
app.include_router(maschinen_router.router)
app.include_router(admin_router.router)
app.include_router(uploads_router.router)

# Statische Frontend-Dateien (JS, CSS, Bilder) unter /static/*.
app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    """SPA-Fallback: alle nicht-API-Pfade liefern die index.html aus.

    /api/* wird vorher von den Routern gefangen; bleibt hier nur, wenn
    ein API-Pfad nicht existiert — dann geben wir 404 (statt index.html).
    """
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API-Endpunkt nicht gefunden.")
    return FileResponse(_INDEX_HTML)
