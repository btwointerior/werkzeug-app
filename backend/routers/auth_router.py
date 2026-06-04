"""Auth-Endpunkte: Login, Logout, eigenes Profil."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import create_access_token
from backend.dependencies import get_current_user
from backend.models import Benutzer, get_db
from backend.schemas import (
    BenutzerKurz,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
)

router = APIRouter(prefix="/api", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(daten: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Meldet einen Benutzer mit Benutzername + Passwort an und liefert ein JWT zurück.

    Gibt 401 zurück, wenn die Zugangsdaten falsch oder der Benutzer gesperrt ist.
    """
    benutzer = (
        db.query(Benutzer).filter(Benutzer.benutzername == daten.benutzername).first()
    )
    if benutzer is None or not benutzer.pruefe_passwort(daten.passwort):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ist falsch.",
        )
    if not benutzer.aktiv:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer ist gesperrt.",
        )

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


@router.get("/me", response_model=BenutzerKurz)
def aktuelles_profil(
    current_user: Benutzer = Depends(get_current_user),
) -> BenutzerKurz:
    """Liefert das Profil des aktuell eingeloggten Benutzers."""
    return BenutzerKurz.model_validate(current_user)
