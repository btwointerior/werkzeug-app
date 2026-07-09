"""JWT-Token erzeugen und validieren.

Zwei Token-Sorten, beide mit demselben SECRET_KEY + Algorithm:
- Login-Token: kein `scope`-Claim (oder anders gesetzt), 30 Tage, sub = Benutzer-ID
- Datei-Token: `scope`="datei", `datei`=Dateiname, 5 Minuten, sub = Benutzer-ID
Per scope-Claim getrennt, damit ein Datei-Token NICHT als Login-Token akzeptiert wird.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from backend.config import settings

_SCOPE_DATEI = "datei"


def create_access_token(benutzer_id: int) -> str:
    """Erzeugt einen Login-JWT mit `sub` = Benutzer-ID und Ablauf nach N Tagen."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.ACCESS_TOKEN_EXPIRE_DAYS
    )
    payload: dict = {
        "sub": str(benutzer_id),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Validiert einen Login-Token und gibt die Benutzer-ID zurück.

    Datei-Tokens (scope="datei") werden hier ausdrücklich abgelehnt.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("scope") == _SCOPE_DATEI:
            return None  # kein Login-Token
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (JWTError, ValueError):
        return None


def token_restlaufzeit(token: str) -> Optional[float]:
    """Restlaufzeit eines Login-Tokens in Sekunden (None bei ungültig/ohne exp)."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None
    if payload.get("scope") == _SCOPE_DATEI:
        return None
    exp = payload.get("exp")
    if exp is None:
        return None
    return exp - datetime.now(timezone.utc).timestamp()


def create_datei_token(benutzer_id: int, datei: str) -> str:
    """Erzeugt einen kurzlebigen Token, der GENAU für die angegebene Datei gilt."""
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=settings.DATEI_TOKEN_EXPIRE_SECONDS
    )
    payload: dict = {
        "sub": str(benutzer_id),
        "scope": _SCOPE_DATEI,
        "datei": datei,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_datei_token(token: str, erwartete_datei: str) -> bool:
    """Prüft, ob der Token ein gültiger Datei-Token für GENAU `erwartete_datei` ist."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return False
    return (
        payload.get("scope") == _SCOPE_DATEI
        and payload.get("datei") == erwartete_datei
    )
