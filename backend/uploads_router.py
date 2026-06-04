"""Auslieferung von Datei-Uploads mit kurzlebigem Datei-Token.

Zwei Endpunkte:
  - GET /api/uploads/token?datei=<name>  (Login-Token, liefert Datei-Token)
  - GET /uploads/{filename}?t=<datei-token>  (öffentlich erreichbar, prüft Datei-Token)

Der Datei-Token ist 5 Minuten gültig und nur für die EINE Datei, für die er
ausgestellt wurde. Damit funktionieren <img src=...> und <a href=... target=_blank>
ohne JS-Verrenkungen, ohne dass der lange Login-Token in der URL landet.
"""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.auth import create_datei_token, decode_datei_token
from backend.config import settings
from backend.dependencies import get_current_user
from backend.models import Benutzer
from backend.schemas import DateiTokenOut


router = APIRouter(tags=["Uploads"])


def _sicherer_name(name: str) -> str:
    """Liefert nur den Basisnamen (kein Pfad), wirft 400 bei verdächtigen Eingaben."""
    sicher = Path(name).name
    if not sicher or sicher != name or sicher.startswith("."):
        raise HTTPException(status_code=400, detail="Ungültiger Dateiname.")
    return sicher


@router.get("/api/uploads/token", response_model=DateiTokenOut)
def hole_datei_token(
    datei: str = Query(..., max_length=200),
    current_user: Benutzer = Depends(get_current_user),
) -> DateiTokenOut:
    """Stellt einen 5-Minuten-Token aus, der nur für DIE eine Datei gilt."""
    sicher = _sicherer_name(datei)
    token = create_datei_token(current_user.id, sicher)
    return DateiTokenOut(
        token=token, expires_in=settings.DATEI_TOKEN_EXPIRE_SECONDS
    )


@router.get("/uploads/{filename}", include_in_schema=False)
def liefere_upload(filename: str, t: str = Query(...)) -> FileResponse:
    """Liefert eine Datei aus, wenn der Datei-Token für GENAU diese Datei gilt."""
    sicher = _sicherer_name(filename)

    if not decode_datei_token(t, sicher):
        raise HTTPException(
            status_code=401, detail="Datei-Token ungültig oder abgelaufen."
        )

    pfad = settings.UPLOAD_DIR / sicher
    if not pfad.is_file():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.")

    # Content-Type aus Endung ableiten; passt für jpg/png/webp/pdf.
    mime, _ = mimetypes.guess_type(str(pfad))
    return FileResponse(
        pfad,
        media_type=mime or "application/octet-stream",
        filename=sicher,
    )
