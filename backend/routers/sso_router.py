"""Portal-SSO (home.b2interior.de): signierte X-B2-Header → Werkzeug-JWT.

Der Pfad liegt bewusst NICHT unter /api/*, damit Caddy ihn hinter den Portal-Torwächter
(forward_auth) legt; die iOS-App nutzt weiterhin /api/login mit Benutzername/Passwort.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend import sso
from backend.auth import create_access_token
from backend.models import Benutzer, Rolle, get_db
from backend.schemas import BenutzerKurz, TokenResponse

router = APIRouter(tags=["Auth"])


@router.get("/sso/token", response_model=TokenResponse, include_in_schema=False)
def sso_token(request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """Tauscht gültige Portal-Header gegen ein Werkzeug-Token (Benutzer per Kürzel)."""
    p = sso.benutzer_aus_headern(request.headers)
    if not p:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Keine Portal-Anmeldung.")
    rolle = Rolle.ADMIN if p["rolle"] == "admin" else Rolle.MITARBEITER
    benutzer = db.query(Benutzer).filter(Benutzer.benutzername.ilike(p["kuerzel"])).first()
    if benutzer is None:
        # Portal ist führend: Benutzer beim ersten Portal-Login anlegen (Zufallspasswort,
        # Login nur über das Portal; Admin kann in der Benutzerverwaltung ein Passwort setzen).
        vor, _, nach = (p.get("name") or p["kuerzel"]).strip().rpartition(" ")
        benutzer = Benutzer(benutzername=p["kuerzel"], vorname=vor or p["kuerzel"], nachname=nach or "-", rolle=rolle, aktiv=True)
        benutzer.setze_passwort(secrets.token_urlsafe(24), merke_klartext=False)
        db.add(benutzer)
        db.commit()
        db.refresh(benutzer)
    elif benutzer.rolle != rolle:
        benutzer.rolle = rolle   # Rolle folgt dem Portal
        db.commit()
        db.refresh(benutzer)
    if not benutzer.aktiv:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Benutzer ist gesperrt.")
    return TokenResponse(access_token=create_access_token(benutzer.id), benutzer=BenutzerKurz.model_validate(benutzer))
