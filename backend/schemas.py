"""
Pydantic v2 Request/Response Schemas.

Response-Modelle, die aus SQLAlchemy-Objekten gelesen werden, erben von `_ORM`
(setzt `from_attributes=True`). Reine Request-Modelle erben von `BaseModel`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models import MaschinenStatus, Rolle, RueckgabeZustand


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============================================================
#  Auth
# ============================================================

class LoginRequest(BaseModel):
    benutzername: str = Field(..., min_length=1, max_length=50)
    passwort: str = Field(..., min_length=1)


class BenutzerKurz(_ORM):
    id: int
    benutzername: str
    vorname: str
    nachname: str
    voller_name: str
    rolle: Rolle
    email: Optional[str] = None
    aktiv: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    benutzer: BenutzerKurz


class LogoutResponse(BaseModel):
    message: str


# ============================================================
#  Zubehör
# ============================================================

class ZubehoerOut(_ORM):
    id: int
    bezeichnung: str


class ZubehoerCreate(BaseModel):
    bezeichnung: str = Field(..., min_length=1, max_length=120)


# ============================================================
#  Maschine
# ============================================================

class AusleiheKurz(_ORM):
    """Reduzierte Ausleih-Info, eingebettet in MaschineOut."""
    id: int
    benutzer_id: int
    benutzer: BenutzerKurz
    ausleih_zeitpunkt: datetime


class MaschineKurz(_ORM):
    id: int
    maschinen_code: str
    name: str
    status: MaschinenStatus


class MaschineOut(_ORM):
    id: int
    maschinen_code: str
    name: str
    platznummer: Optional[str] = None
    hersteller: Optional[str] = None
    seriennummer: Optional[str] = None
    beschreibung: Optional[str] = None
    foto_pfad: Optional[str] = None
    anleitung_pfad: Optional[str] = None
    # Fertige URLs inkl. kurzlebigem Datei-Token (vom Router befüllt, nicht aus DB)
    foto_url: Optional[str] = None
    anleitung_url: Optional[str] = None
    status: MaschinenStatus
    erstellt_am: datetime
    geaendert_am: datetime
    zubehoer_liste: list[ZubehoerOut] = []
    aktuelle_ausleihe: Optional[AusleiheKurz] = None


class MaschineCreate(BaseModel):
    maschinen_code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=120)
    platznummer: Optional[str] = Field(None, max_length=50)
    hersteller: Optional[str] = Field(None, max_length=80)
    seriennummer: Optional[str] = Field(None, max_length=80)
    beschreibung: Optional[str] = None
    foto_pfad: Optional[str] = Field(None, max_length=255)
    anleitung_pfad: Optional[str] = Field(None, max_length=255)
    status: MaschinenStatus = MaschinenStatus.VERFUEGBAR
    zubehoer: list[ZubehoerCreate] = []


class MaschineUpdate(BaseModel):
    """Alle Felder optional. Nicht gesendete Felder bleiben unverändert.
    Für `zubehoer`: None = nicht anfassen; [] = alles Zubehör entfernen;
    Liste = vollständiger Ersatz."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    platznummer: Optional[str] = Field(None, max_length=50)
    hersteller: Optional[str] = Field(None, max_length=80)
    seriennummer: Optional[str] = Field(None, max_length=80)
    beschreibung: Optional[str] = None
    foto_pfad: Optional[str] = Field(None, max_length=255)
    anleitung_pfad: Optional[str] = Field(None, max_length=255)
    status: Optional[MaschinenStatus] = None
    zubehoer: Optional[list[ZubehoerCreate]] = None


# ============================================================
#  Ausleihe
# ============================================================

class AusleihenRequest(BaseModel):
    """Beim Ausleihen mitgenommenes Zubehör (Bezeichnungen aus der Maschinen-Liste)."""
    zubehoer_bezeichnungen: list[str] = []


class ZurueckgabeRequest(BaseModel):
    zustand: RueckgabeZustand
    kommentar: Optional[str] = None


class MeineAusleiheOut(_ORM):
    """Offene Ausleihe des aktuellen Mitarbeiters."""
    id: int
    ausleih_zeitpunkt: datetime
    dauer_tage: int
    maschine: MaschineKurz


class AusleiheHistorieOut(_ORM):
    """Eintrag in der Maschinen-Historie (Admin)."""
    id: int
    benutzer: BenutzerKurz
    ausleih_zeitpunkt: datetime
    rueckgabe_zeitpunkt: Optional[datetime] = None
    rueckgabe_zustand: Optional[RueckgabeZustand] = None
    rueckgabe_kommentar: Optional[str] = None
    dauer_tage: int
    ist_offen: bool


# ============================================================
#  Benutzer (Admin)
# ============================================================

class BenutzerOut(_ORM):
    id: int
    benutzername: str
    vorname: str
    nachname: str
    voller_name: str
    rolle: Rolle
    email: Optional[str] = None
    aktiv: bool
    erstellt_am: datetime


class BenutzerCreate(BaseModel):
    benutzername: str = Field(..., min_length=1, max_length=50)
    vorname: str = Field(..., min_length=1, max_length=50)
    nachname: str = Field(..., min_length=1, max_length=50)
    passwort: str = Field(..., min_length=4)
    rolle: Rolle = Rolle.MITARBEITER
    email: Optional[str] = Field(None, max_length=120)


class BenutzerUpdate(BaseModel):
    vorname: Optional[str] = Field(None, min_length=1, max_length=50)
    nachname: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, max_length=120)
    rolle: Optional[Rolle] = None
    aktiv: Optional[bool] = None
    neues_passwort: Optional[str] = Field(None, min_length=4)


# ============================================================
#  Statistiken
# ============================================================

class TopMaschineEintrag(BaseModel):
    id: int
    maschinen_code: str
    name: str
    anzahl_ausleihen: int


class UeberfaelligeAusleiheEintrag(BaseModel):
    id: int
    maschine: MaschineKurz
    benutzer: BenutzerKurz
    ausleih_zeitpunkt: datetime
    dauer_tage: int


class StatistikenOut(BaseModel):
    top_maschinen: list[TopMaschineEintrag]
    ueberfaellige: list[UeberfaelligeAusleiheEintrag]


# ============================================================
#  Uploads / QR-Codes
# ============================================================

class DateiTokenOut(BaseModel):
    token: str
    expires_in: int


class SammeldruckRequest(BaseModel):
    maschine_ids: list[int] = Field(..., min_length=1, max_length=200)
