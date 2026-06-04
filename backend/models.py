"""
Datenmodell für die Werkzeug-Ausleih-App
=========================================

Tabellen:
- Benutzer     : Mitarbeiter und Admins
- Maschine     : Inventar aller Handmaschinen
- Ausleihe     : Historie aller Ausleihvorgänge (aktuell + vergangen)
- Zubehoer     : Zubehörteile pro Maschine (z.B. Akku, Ladegerät)
"""

from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    ForeignKey, Boolean, Text, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from passlib.context import CryptContext

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --------------------------------------------------------------------
#  ENUMs - feste Status-Werte
# --------------------------------------------------------------------

class Rolle(str, Enum):
    """Rolle eines Benutzers im System."""
    MITARBEITER = "mitarbeiter"
    ADMIN = "admin"


class MaschinenStatus(str, Enum):
    """Aktueller Zustand einer Maschine."""
    VERFUEGBAR = "verfuegbar"     # kann ausgeliehen werden
    AUSGELIEHEN = "ausgeliehen"   # gerade in Benutzung
    DEFEKT = "defekt"             # gesperrt, nur Admin kann freigeben
    WARTUNG = "wartung"           # in Wartung, gesperrt


class RueckgabeZustand(str, Enum):
    """Zustand bei der Rückgabe einer Maschine."""
    OK = "ok"                     # alles in Ordnung
    DEFEKT = "defekt"             # Maschine ist kaputt
    WARTUNG_NOETIG = "wartung"    # Wartung erforderlich


# --------------------------------------------------------------------
#  Benutzer (Mitarbeiter / Admin)
# --------------------------------------------------------------------

class Benutzer(Base):
    __tablename__ = "benutzer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    benutzername = Column(String(50), unique=True, nullable=False, index=True)
    vorname = Column(String(50), nullable=False)
    nachname = Column(String(50), nullable=False)
    passwort_hash = Column(String(255), nullable=False)
    rolle = Column(SQLEnum(Rolle), default=Rolle.MITARBEITER, nullable=False)
    email = Column(String(120), nullable=True)  # für Erinnerungs-Mails
    aktiv = Column(Boolean, default=True, nullable=False)
    erstellt_am = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Beziehung: alle Ausleihen dieses Nutzers
    ausleihen = relationship("Ausleihe", back_populates="benutzer")

    @property
    def voller_name(self) -> str:
        return f"{self.vorname} {self.nachname}"

    def setze_passwort(self, klartext: str) -> None:
        """Passwort als Hash speichern (niemals im Klartext!)."""
        self.passwort_hash = pwd_context.hash(klartext)

    def pruefe_passwort(self, klartext: str) -> bool:
        """Eingegebenes Passwort gegen Hash prüfen."""
        return pwd_context.verify(klartext, self.passwort_hash)

    @property
    def ist_admin(self) -> bool:
        return self.rolle == Rolle.ADMIN

    def __repr__(self) -> str:
        return f"<Benutzer {self.benutzername} ({self.rolle.value})>"


# --------------------------------------------------------------------
#  Maschine
# --------------------------------------------------------------------

class Maschine(Base):
    __tablename__ = "maschinen"

    id = Column(Integer, primary_key=True, autoincrement=True)
    maschinen_code = Column(String(20), unique=True, nullable=False, index=True)
    # ^^ z.B. "M-0042" - dieser Code steht im QR-Code

    name = Column(String(120), nullable=False)
    platznummer = Column(String(50), nullable=True)
    hersteller = Column(String(80), nullable=True)
    seriennummer = Column(String(80), nullable=True)
    beschreibung = Column(Text, nullable=True)

    # Datei-Pfade (relativ zum uploads/-Ordner)
    foto_pfad = Column(String(255), nullable=True)
    anleitung_pfad = Column(String(255), nullable=True)

    status = Column(
        SQLEnum(MaschinenStatus),
        default=MaschinenStatus.VERFUEGBAR,
        nullable=False,
        index=True,
    )

    erstellt_am = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    geaendert_am = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Beziehungen
    zubehoer_liste = relationship(
        "Zubehoer",
        back_populates="maschine",
        cascade="all, delete-orphan",
    )
    ausleihen = relationship(
        "Ausleihe",
        back_populates="maschine",
        order_by="Ausleihe.ausleih_zeitpunkt.desc()",
    )

    @property
    def aktuelle_ausleihe(self):
        """Gibt die aktuell offene Ausleihe zurück (oder None)."""
        for a in self.ausleihen:
            if a.rueckgabe_zeitpunkt is None:
                return a
        return None

    @property
    def letzte_ausleihe(self):
        """Gibt die zuletzt abgeschlossene Ausleihe zurück (oder None)."""
        for a in self.ausleihen:
            if a.rueckgabe_zeitpunkt is not None:
                return a
        return None

    @property
    def ist_verfuegbar(self) -> bool:
        return self.status == MaschinenStatus.VERFUEGBAR

    def __repr__(self) -> str:
        return f"<Maschine {self.maschinen_code} '{self.name}' [{self.status.value}]>"


# --------------------------------------------------------------------
#  Zubehör (1 Maschine -> N Zubehörteile)
# --------------------------------------------------------------------

class Zubehoer(Base):
    __tablename__ = "zubehoer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    maschine_id = Column(
        Integer,
        ForeignKey("maschinen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bezeichnung = Column(String(120), nullable=False)
    # z.B. "2 Akkus 18V", "Ladegerät", "Koffer", "Bohrer-Set"

    maschine = relationship("Maschine", back_populates="zubehoer_liste")

    def __repr__(self) -> str:
        return f"<Zubehoer '{self.bezeichnung}'>"


# --------------------------------------------------------------------
#  Ausleihe - Historie aller Vorgänge
# --------------------------------------------------------------------

class Ausleihe(Base):
    __tablename__ = "ausleihen"

    id = Column(Integer, primary_key=True, autoincrement=True)
    maschine_id = Column(
        Integer,
        ForeignKey("maschinen.id"),
        nullable=False,
        index=True,
    )
    benutzer_id = Column(
        Integer,
        ForeignKey("benutzer.id"),
        nullable=False,
        index=True,
    )

    ausleih_zeitpunkt = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    rueckgabe_zeitpunkt = Column(DateTime, nullable=True)
    # ^^ NULL = noch nicht zurückgegeben (= aktuell ausgeliehen)

    rueckgabe_zustand = Column(SQLEnum(RueckgabeZustand), nullable=True)
    rueckgabe_kommentar = Column(Text, nullable=True)

    # Erinnerung: wann wurde zuletzt eine Mahnung verschickt?
    letzte_erinnerung_am = Column(DateTime, nullable=True)

    # Beziehungen
    maschine = relationship("Maschine", back_populates="ausleihen")
    benutzer = relationship("Benutzer", back_populates="ausleihen")

    @property
    def ist_offen(self) -> bool:
        return self.rueckgabe_zeitpunkt is None

    @property
    def dauer_tage(self) -> int:
        ende = self.rueckgabe_zeitpunkt or datetime.now(timezone.utc).replace(tzinfo=None)
        return (ende - self.ausleih_zeitpunkt).days

    def __repr__(self) -> str:
        zustand = "offen" if self.ist_offen else "abgeschlossen"
        return f"<Ausleihe #{self.id} [{zustand}]>"


# --------------------------------------------------------------------
#  Datenbank-Setup
# --------------------------------------------------------------------

DATABASE_URL = "sqlite:///./data/werkzeug.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # nötig für FastAPI + SQLite
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Erstellt alle Tabellen, falls sie noch nicht existieren."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency für FastAPI - stellt eine DB-Session bereit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
