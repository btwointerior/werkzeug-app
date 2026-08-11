"""Auth-Endpunkte: Login, Logout, eigenes Profil."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend import rate_limit
from backend.auth import create_access_token
from backend.dependencies import get_current_user
from backend.models import Benutzer, get_db
from backend.schemas import (
    BenutzerKurz,
    LoginRequest,
    LogoutResponse,
    PasswortAendernRequest,
    PasswortAendernResponse,
    TokenResponse,
)

router = APIRouter(prefix="/api", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    daten: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """Meldet einen Benutzer mit Benutzername + Passwort an und liefert ein JWT zurück.

    Gibt 401 zurück, wenn die Zugangsdaten falsch oder der Benutzer gesperrt ist,
    und 429, wenn zu viele Fehlversuche vorliegen (Brute-Force-Schutz).
    """
    ip = request.client.host if request.client else "unbekannt"
    drossel_key = f"{ip}:{daten.benutzername}"
    rate_limit.pruefe(drossel_key)

    benutzer = (
        db.query(Benutzer).filter(Benutzer.benutzername == daten.benutzername).first()
    )
    if benutzer is None or not benutzer.pruefe_passwort(daten.passwort):
        rate_limit.merke_fehlversuch(drossel_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ist falsch.",
        )
    if not benutzer.aktiv:
        rate_limit.merke_fehlversuch(drossel_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer ist gesperrt.",
        )

    rate_limit.reset(drossel_key)
    token = create_access_token(benutzer.id)
    return TokenResponse(
        access_token=token,
        benutzer=BenutzerKurz.model_validate(benutzer),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(_: Benutzer = Depends(get_current_user)) -> LogoutResponse:
    """Logout-Hinweis. JWT ist zustandslos — der Client muss den Token verwerfen."""
    return LogoutResponse(
        message="Logout erfolgreich. Token bitte clientseitig löschen."
    )


@router.post("/passwort-aendern", response_model=PasswortAendernResponse)
def passwort_aendern(
    daten: PasswortAendernRequest,
    request: Request,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PasswortAendernResponse:
    """Ändert das eigene Passwort (jeder eingeloggte Benutzer).

    Das aktuelle Passwort ist Pflicht (Schutz bei offen liegendem Gerät) und
    läuft über dieselbe Brute-Force-Drossel wie der Login. Nach der Änderung
    wird der Klartext gelöscht — der Admin sieht das Passwort nicht mehr,
    kann aber weiterhin ein neues setzen (dann wieder mit Klartext-Anzeige).
    """
    ip = request.client.host if request.client else "unbekannt"
    drossel_key = f"pwae:{ip}:{current_user.benutzername}"
    rate_limit.pruefe(drossel_key)

    if not current_user.pruefe_passwort(daten.aktuelles_passwort):
        rate_limit.merke_fehlversuch(drossel_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das aktuelle Passwort ist falsch.",
        )

    rate_limit.reset(drossel_key)
    current_user.setze_passwort(daten.neues_passwort, merke_klartext=False)
    db.commit()
    return PasswortAendernResponse(message="Passwort erfolgreich geändert.")


@router.get("/me", response_model=BenutzerKurz)
def aktuelles_profil(
    current_user: Benutzer = Depends(get_current_user),
) -> BenutzerKurz:
    """Liefert das Profil des aktuell eingeloggten Benutzers."""
    return BenutzerKurz.model_validate(current_user)
