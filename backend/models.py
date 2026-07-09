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
    create_engine, event, text, Column, Integer, String, DateTime,
    ForeignKey, Boolean, Text, Enum as SQLEnum, Index
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from passlib.context import CryptContext

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _naiv(dt: datetime | None) -> datetime | None:
    """Entfernt die Zeitzoneninfo (auf naiv), damit naive/aware nicht gemischt werden."""
    if dt is not None and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, connection_record):
    """Aktiviert Foreign-Key-Enforcement für SQLite (standardmäßig AUS).

    Ohne dieses PRAGMA greifen die ondelete-Kaskaden nicht. Gilt für alle
    SQLite-Verbindungen (App und Tests); andere Backends bleiben unberührt.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
    # ACHTUNG: Klartext-Passwort auf ausdrücklichen Wunsch des Betreibers, damit Admins es
    # ansehen können. Bewusst gegen die Sicherheitsempfehlung: bei einem DB-/Backup-Leak
    # liegen alle so gespeicherten Passwörter offen. Nur ab Einführung neu gesetzte Passwörter
    # sind befüllt (Alt-Hashes sind nicht rückrechenbar).
    passwort_klartext = Column(String(255), nullable=True)
    rolle = Column(SQLEnum(Rolle), default=Rolle.MITARBEITER, nullable=False)
    email = Column(String(120), nullable=True)  # für Erinnerungs-Mails
    aktiv = Column(Boolean, default=True, nullable=False)
    erstellt_am = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Beziehung: alle Ausleihen dieses Nutzers.
    # KEIN passive_deletes: das ORM löscht die Kinder selbst, damit das Löschen
    # auch auf der Alt-Prod-DB funktioniert (deren Tabellen tragen die
    # ondelete-CASCADE-Regel nicht; create_all zieht sie nicht nach).
    ausleihen = relationship(
        "Ausleihe",
        back_populates="benutzer",
        cascade="all, delete-orphan",
    )

    @property
    def voller_name(self) -> str:
        return f"{self.vorname} {self.nachname}"

    def setze_passwort(self, klartext: str) -> None:
        """Passwort als Hash speichern (für die Anmeldung maßgeblich) UND zusätzlich im
        Klartext (siehe passwort_klartext) für die Admin-Anzeige."""
        self.passwort_hash = pwd_context.hash(klartext)
        self.passwort_klartext = klartext

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
        # KEIN passive_deletes (siehe Benutzer.ausleihen): ORM löscht die Historie
        # selbst, damit das Löschen auf der Alt-Prod-DB ohne DB-Kaskade klappt.
        cascade="all, delete-orphan",
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

    # Absicherung gegen die Doppel-Ausleihe-Race: pro Maschine darf höchstens
    # eine Ausleihe offen sein (rueckgabe_zeitpunkt IS NULL). Der Statuscheck im
    # Router allein reicht bei parallelen Requests nicht — dieser partielle
    # Unique-Index ist die verlässliche Barriere.
    __table_args__ = (
        Index(
            "uq_offene_ausleihe_pro_maschine",
            "maschine_id",
            unique=True,
            sqlite_where=text("rueckgabe_zeitpunkt IS NULL"),
            postgresql_where=text("rueckgabe_zeitpunkt IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    maschine_id = Column(
        Integer,
        ForeignKey("maschinen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    benutzer_id = Column(
        Integer,
        ForeignKey("benutzer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ausleih_zeitpunkt = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    rueckgabe_zeitpunkt = Column(DateTime, nullable=True, index=True)
    # ^^ NULL = noch nicht zurückgegeben (= aktuell ausgeliehen)

    rueckgabe_zustand = Column(SQLEnum(RueckgabeZustand), nullable=True)
    rueckgabe_kommentar = Column(Text, nullable=True)

    # Erinnerung: wann wurde zuletzt eine Mahnung verschickt?
    letzte_erinnerung_am = Column(DateTime, nullable=True)

    # Beziehungen
    maschine = relationship("Maschine", back_populates="ausleihen")
    benutzer = relationship("Benutzer", back_populates="ausleihen")
    mitgenommenes_zubehoer = relationship(
        "AusleiheZubehoer",
        back_populates="ausleihe",
        cascade="all, delete-orphan",
    )

    # Empfänger: NULL = für den ausleihenden Mitarbeiter selbst;
    # gesetzt = für ein externes Montageteam.
    externes_team_id = Column(
        Integer, ForeignKey("externe_teams.id"), nullable=True, index=True
    )
    externes_team = relationship("ExternesTeam", back_populates="ausleihen")

    @property
    def externes_team_name(self) -> str | None:
        return self.externes_team.name if self.externes_team else None

    @property
    def ist_offen(self) -> bool:
        return self.rueckgabe_zeitpunkt is None

    @property
    def dauer_tage(self) -> int:
        # SQLite legt datetimes ohne tz ab; frisch erzeugte Objekte tragen aber
        # aware UTC (siehe Column-Default). Beide Seiten auf naiv normalisieren,
        # sonst wirft die Subtraktion "can't subtract naive and aware".
        start = _naiv(self.ausleih_zeitpunkt)
        ende = _naiv(self.rueckgabe_zeitpunkt) or datetime.now(timezone.utc).replace(tzinfo=None)
        return (ende - start).days

    def __repr__(self) -> str:
        zustand = "offen" if self.ist_offen else "abgeschlossen"
        return f"<Ausleihe #{self.id} [{zustand}]>"


# --------------------------------------------------------------------
#  AusleiheZubehoer - Mitnahme-Protokoll pro Ausleihe
# --------------------------------------------------------------------

class AusleiheZubehoer(Base):
    """Schnappschuss eines beim Ausleihen mitgenommenen Zubehörteils.

    Der Name wird kopiert (nicht per FK verlinkt), damit das Protokoll
    unveränderlich bleibt, auch wenn der Admin das Zubehör der Maschine
    später ändert oder löscht.
    """
    __tablename__ = "ausleihe_zubehoer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ausleihe_id = Column(
        Integer,
        ForeignKey("ausleihen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bezeichnung = Column(String(120), nullable=False)
    # NULL = Rückgabe noch offen; True/False wird bei der Rückgabe gesetzt
    zurueckgebracht = Column(Boolean, nullable=True)

    ausleihe = relationship("Ausleihe", back_populates="mitgenommenes_zubehoer")

    def __repr__(self) -> str:
        return f"<AusleiheZubehoer '{self.bezeichnung}'>"


# --------------------------------------------------------------------
#  ExternesTeam - externe Montageteams (Empfänger einer Ausleihe)
# --------------------------------------------------------------------

class ExternesTeam(Base):
    """Externes Montageteam, für das eine Maschine ausgeliehen werden kann.

    Wird beim Ausleihen automatisch angelegt (find-or-create), sobald ein
    neuer Team-Name verwendet wird. Der eindeutige Name speist das Dropdown.
    """
    __tablename__ = "externe_teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True, index=True)

    ausleihen = relationship("Ausleihe", back_populates="externes_team")

    def __repr__(self) -> str:
        return f"<ExternesTeam '{self.name}'>"


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
