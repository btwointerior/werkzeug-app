"""FastAPI-App für die Werkzeug-Ausleihe."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.auth import create_access_token, decode_access_token, token_restlaufzeit
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
    # Bearer-Token statt Cookie -> keine Credentials nötig; erlaubt strikte Origins.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-New-Token"],
)

# Security-Header, die für die ganze API/Frontend-Auslieferung gelten sollen.
# CSP lässt Tailwind-CDN + eigene Skripte/Bilder zu und erlaubt PDF-/Blob-Vorschau.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "frame-src 'self' blob:; "
    "object-src 'self' blob:; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Setzt Defense-in-Depth-Header auf jede Antwort."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    return response


@app.middleware("http")
async def sliding_token_middleware(request: Request, call_next):
    """Verlängert den Login-Token, wenn er bald abläuft (nur auf API-Pfaden).

    Der neue Token wird im Response-Header `X-New-Token` zurückgegeben. Anders als
    früher wird NICHT bei jedem Request erneuert, sondern nur, wenn die Restlaufzeit
    unter die konfigurierte Schwelle fällt — spart Arbeit und vermeidet, dass jeder
    Request (auch statische Dateien) einen neuen Token bekommt.
    """
    response = await call_next(request)
    if response.status_code < 400 and request.url.path.startswith("/api/"):
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            benutzer_id = decode_access_token(token)
            rest = token_restlaufzeit(token)
            if (
                benutzer_id is not None
                and rest is not None
                and rest < settings.TOKEN_REFRESH_SCHWELLE_SEKUNDEN
            ):
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
