"""Datenmodell „Schneidwerkzeuge" (Maschinenwerkzeuge: Sägeblätter, Fräser, …).

Zweiter Bereich neben der Geräte-Ausleihe. Stufe 1: Bestand je Einzelwerkzeug, Status/Ort,
Schärfkreislauf (Auftrag → Rückkehr mit Kosten) und Verlauf.

Tabellen:
- Schneidwerkzeug         : ein einzelnes Werkzeug mit Stammdaten, Status und Ort
- SchneidwerkzeugEreignis : Verlauf (angelegt, Statuswechsel, Schärfdienst)
- SchaerfAuftrag          : eine Abgabe an den Schärfdienst
- SchaerfPosition         : ein Werkzeug in einem Schärfauftrag (Rückkehr, Kosten, Ergebnis)

Status und Art sind einfache Texte (keine DB-Enums), damit neue Werte ohne Migration möglich sind.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.models import Base

# Art → (Bezeichnung, Code-Präfix). Der Präfix unterscheidet die Codes von Geräten (M-…).
ARTEN = {
    "saegeblatt": ("Sägeblatt", "SB"),
    "vorritzer": ("Vorritzer", "VR"),
    "fraeser": ("Fräser", "FR"),
    "bohrer": ("Bohrer", "BO"),
    "messer": ("Messer / Wendeplatte", "ME"),
    "sonstiges": ("Sonstiges", "SW"),
}

STATUS_LAGER = "lager"
STATUS_MASCHINE = "maschine"
STATUS_STUMPF = "stumpf"
STATUS_SCHAERFDIENST = "schaerfdienst"
STATUS_GESPERRT = "gesperrt"
STATUS_VERSCHROTTET = "verschrottet"
STATUS = {
    STATUS_LAGER: "Im Lager (scharf)",
    STATUS_MASCHINE: "In Maschine",
    STATUS_STUMPF: "Stumpf",
    STATUS_SCHAERFDIENST: "Beim Schärfdienst",
    STATUS_GESPERRT: "Gesperrt",
    STATUS_VERSCHROTTET: "Verschrottet",
}

ERGEBNIS_GESCHAERFT = "geschaerft"
ERGEBNIS_AUSGEMUSTERT = "ausgemustert"


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


class Schneidwerkzeug(Base):
    __tablename__ = "schneidwerkzeuge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    art = Column(String(20), nullable=False, index=True)
    bezeichnung = Column(String(200), nullable=False)
    hersteller = Column(String(120), nullable=True)
    artikelnummer = Column(String(80), nullable=True, index=True)
    schneidstoff = Column(String(20), nullable=True)  # HW, DP, HSS …
    durchmesser_mm = Column(Float, nullable=True)
    schneidenlaenge_mm = Column(Float, nullable=True)  # Fräser: Nutzlänge; Sägeblatt: Schnittbreite
    bohrung_schaft_mm = Column(Float, nullable=True)   # Sägeblatt: Bohrung; Fräser: Schaft
    zaehnezahl = Column(Integer, nullable=True)
    max_drehzahl = Column(Integer, nullable=True)      # n max laut Werkzeug (1/min)
    max_schaerfungen = Column(Integer, nullable=True)  # wie oft insgesamt schärfbar
    kaufdatum = Column(Date, nullable=True)
    kaufpreis_cent = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default=STATUS_LAGER, index=True)
    lagerort = Column(String(80), nullable=True)       # Fach/Platz im Lager
    maschine = Column(String(80), nullable=True)       # in welcher Maschine eingebaut
    platz = Column(String(40), nullable=True)          # Werkzeugplatz/-nummer in der Maschine
    partner_id = Column(Integer, ForeignKey("schneidwerkzeuge.id", ondelete="SET NULL"), nullable=True)
    notiz = Column(Text, nullable=True)
    erstellt_am = Column(DateTime, default=_jetzt, nullable=False)

    # Satz (z. B. Sägeblatt + Vorritzer): die Verknüpfung steht nur bei einem der beiden, gilt aber in beide Richtungen.
    partner = relationship("Schneidwerkzeug", remote_side=[id], foreign_keys=[partner_id], backref="partner_von")
    ereignisse = relationship(
        "SchneidwerkzeugEreignis", back_populates="werkzeug",
        order_by="SchneidwerkzeugEreignis.id.desc()", cascade="all, delete-orphan",
    )
    schaerfpositionen = relationship(
        "SchaerfPosition", back_populates="werkzeug", order_by="SchaerfPosition.id.desc()",
    )

    @property
    def art_text(self) -> str:
        return ARTEN.get(self.art, (self.art, ""))[0]

    @property
    def status_text(self) -> str:
        return STATUS.get(self.status, self.status)

    @property
    def partner_code(self) -> str | None:
        if self.partner:
            return self.partner.code
        return self.partner_von[0].code if self.partner_von else None

    @property
    def anzahl_schaerfungen(self) -> int:
        return sum(1 for p in self.schaerfpositionen if p.ergebnis == ERGEBNIS_GESCHAERFT)

    @property
    def rest_schaerfungen(self) -> int | None:
        if self.max_schaerfungen is None:
            return None
        return max(0, self.max_schaerfungen - self.anzahl_schaerfungen)

    @property
    def schaerfkosten_cent(self) -> int:
        return sum(p.kosten_cent or 0 for p in self.schaerfpositionen)

    def __repr__(self) -> str:
        return f"<Schneidwerkzeug {self.code} '{self.bezeichnung[:30]}' [{self.status}]>"


class SchneidwerkzeugEreignis(Base):
    __tablename__ = "schneidwerkzeug_ereignisse"

    id = Column(Integer, primary_key=True, autoincrement=True)
    werkzeug_id = Column(
        Integer, ForeignKey("schneidwerkzeuge.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    zeitpunkt = Column(DateTime, default=_jetzt, nullable=False)
    benutzer_id = Column(Integer, ForeignKey("benutzer.id", ondelete="SET NULL"), nullable=True)
    art = Column(String(30), nullable=False)  # angelegt | status | geaendert | schaerf_abgabe | schaerf_rueckgabe
    text = Column(Text, nullable=False)

    werkzeug = relationship("Schneidwerkzeug", back_populates="ereignisse")
    benutzer = relationship("Benutzer")

    @property
    def benutzer_name(self) -> str | None:
        return self.benutzer.voller_name if self.benutzer else None


class SchaerfAuftrag(Base):
    __tablename__ = "schaerf_auftraege"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dienst = Column(String(120), nullable=False)
    abgabe_zeitpunkt = Column(DateTime, default=_jetzt, nullable=False, index=True)
    abgeschlossen_am = Column(DateTime, nullable=True, index=True)
    notiz = Column(Text, nullable=True)
    erstellt_von_id = Column(Integer, ForeignKey("benutzer.id", ondelete="SET NULL"), nullable=True)

    erstellt_von = relationship("Benutzer")
    positionen = relationship(
        "SchaerfPosition", back_populates="auftrag", order_by="SchaerfPosition.id",
        cascade="all, delete-orphan",
    )

    @property
    def ist_offen(self) -> bool:
        return self.abgeschlossen_am is None

    @property
    def anzahl(self) -> int:
        return len(self.positionen)

    @property
    def anzahl_zurueck(self) -> int:
        return sum(1 for p in self.positionen if p.zurueck_am is not None)

    @property
    def kosten_cent(self) -> int:
        return sum(p.kosten_cent or 0 for p in self.positionen)


class SchaerfPosition(Base):
    __tablename__ = "schaerf_positionen"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auftrag_id = Column(
        Integer, ForeignKey("schaerf_auftraege.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    werkzeug_id = Column(Integer, ForeignKey("schneidwerkzeuge.id"), nullable=False, index=True)
    zurueck_am = Column(DateTime, nullable=True)
    ergebnis = Column(String(20), nullable=True)  # geschaerft | ausgemustert
    kosten_cent = Column(Integer, nullable=True)
    notiz = Column(Text, nullable=True)

    auftrag = relationship("SchaerfAuftrag", back_populates="positionen")
    werkzeug = relationship("Schneidwerkzeug", back_populates="schaerfpositionen")

    @property
    def werkzeug_code(self) -> str:
        return self.werkzeug.code

    @property
    def werkzeug_bezeichnung(self) -> str:
        return self.werkzeug.bezeichnung

    @property
    def dienst(self) -> str:
        return self.auftrag.dienst

    @property
    def abgabe_zeitpunkt(self) -> datetime:
        return self.auftrag.abgabe_zeitpunkt
