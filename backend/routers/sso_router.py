"""Portal-SSO (home.b2interior.de): signierte X-B2-Header → Werkzeug-JWT.

Der Pfad liegt bewusst NICHT unter /api/*, damit Caddy ihn hinter den Portal-Torwächter
(forward_auth) legt; die iOS-App nutzt weiterhin /api/login mit Benutzername/Passwort.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend import sso
from backend.auth import create_access_token
from backend.models import Benutzer, get_db
from backend.schemas import BenutzerKurz, TokenResponse

router = APIRouter(tags=["Auth"])


@router.get("/sso/token", response_model=TokenResponse, include_in_schema=False)
def sso_token(request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """Tauscht gültige Portal-Header gegen ein Werkzeug-Token (Benutzer per Kürzel)."""
    p = sso.benutzer_aus_headern(request.headers)
    if not p:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Keine Portal-Anmeldung.")
    benutzer = db.query(Benutzer).filter(Benutzer.benutzername.ilike(p["kuerzel"])).first()
    if benutzer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Für das Portal-Kürzel „{p['kuerzel']}“ gibt es in Werkzeug keinen Benutzer.",
        )
    if not benutzer.aktiv:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Benutzer ist gesperrt.")
    return TokenResponse(access_token=create_access_token(benutzer.id), benutzer=BenutzerKurz.model_validate(benutzer))
