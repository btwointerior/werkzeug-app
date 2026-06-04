"""FastAPI-Dependencies: aktuellen Benutzer ermitteln + Admin-Check."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth import decode_access_token
from backend.models import Benutzer, Rolle, get_db


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Benutzer:
    """Liest den Bearer-Token, validiert ihn und gibt den eingeloggten Benutzer zurück.

    Wirft 401 bei fehlendem/ungültigem Token oder gesperrtem Benutzer.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht angemeldet.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    benutzer_id = decode_access_token(credentials.credentials)
    if benutzer_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ungültig oder abgelaufen.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    benutzer = db.query(Benutzer).filter(Benutzer.id == benutzer_id).first()
    if benutzer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer existiert nicht mehr.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not benutzer.aktiv:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer ist gesperrt.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return benutzer


def require_admin(current_user: Benutzer = Depends(get_current_user)) -> Benutzer:
    """Stellt sicher, dass der aktuelle Benutzer Admin-Rechte hat. Sonst 403."""
    if current_user.rolle != Rolle.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-Rechte erforderlich.",
        )
    return current_user
