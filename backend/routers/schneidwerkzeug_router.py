"""Schneidwerkzeuge (Sägeblätter, Fräser, …): Bestand, Status/Ort, Schärfkreislauf.

Rechte: Alle Angemeldeten sehen den Bestand und buchen Statuswechsel (einbauen, ausbauen,
stumpf melden, sperren). Anlegen, Ändern, Löschen/Verschrotten und Schärfaufträge: nur Admin.
"""

import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from backend import qr
from backend.dependencies import get_current_user, require_admin
from backend.models import Benutzer, Rolle, get_db
from backend.schneidwerkzeug_models import (
    ARTEN, ARTEN_MIT_MASSPRUEFUNG, ERGEBNIS_AUSGEMUSTERT, ERGEBNIS_GESCHAERFT, ERGEBNIS_NEU_BESTUECKT, ERGEBNISSE,
    MATERIALIEN, STANDARD_DIENSTE, STANDARD_MASCHINEN, STATUS, STATUS_GESPERRT, STATUS_LAGER,
    STATUS_MASCHINE, STATUS_SCHAERFDIENST, STATUS_STUMPF, STATUS_VERSCHROTTET,
    SchaerfAuftrag, SchaerfPosition, Schneidwerkzeug, SchneidwerkzeugEreignis,
    VerbrauchsBewegung, Verbrauchsteil, WerkstattMaschine,
)

router = APIRouter(prefix="/api/schneidwerkzeuge", tags=["Schneidwerkzeuge"])
schaerf_router = APIRouter(prefix="/api/schaerfauftraege", tags=["Schärfaufträge"])
verbrauch_router = APIRouter(prefix="/api/verbrauchsteile", tags=["Verbrauchsteile"])

CODE_RE = re.compile(r"^[A-Z]{2}-\d{3,5}$")


# --------------------------------------------------------------------------------------
#  Schemas
# --------------------------------------------------------------------------------------

class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WerkzeugEingabe(BaseModel):
    code: Optional[str] = Field(None, max_length=20)  # leer = nächster freier Code der Art
    art: str
    bezeichnung: str = Field(..., min_length=1, max_length=200)
    hersteller: Optional[str] = Field(None, max_length=120)
    artikelnummer: Optional[str] = Field(None, max_length=80)
    schneidstoff: Optional[str] = Field(None, max_length=20)
    durchmesser_mm: Optional[float] = Field(None, ge=0, le=2000)
    schneidenlaenge_mm: Optional[float] = Field(None, ge=0, le=2000)
    bohrung_schaft_mm: Optional[float] = Field(None, ge=0, le=500)
    zaehnezahl: Optional[int] = Field(None, ge=0, le=1000)
    max_drehzahl: Optional[int] = Field(None, ge=0, le=100000)
    max_schaerfungen: Optional[int] = Field(None, ge=0, le=200)
    kaufdatum: Optional[date] = None
    kaufpreis_cent: Optional[int] = Field(None, ge=0, le=100_000_00)
    lagerort: Optional[str] = Field(None, max_length=80)
    partner_code: Optional[str] = Field(None, max_length=20)
    notiz: Optional[str] = Field(None, max_length=2000)
    einsatzgebiet: Optional[str] = Field(None, max_length=1000)
    materialien: Optional[str] = Field(None, max_length=300)
    drehzahl_empfohlen: Optional[int] = Field(None, ge=0, le=100000)
    vorschub_empfohlen: Optional[float] = Field(None, ge=0, le=500)
    parameter_notiz: Optional[str] = Field(None, max_length=1000)


class StatusEingabe(BaseModel):
    status: str
    maschine: Optional[str] = Field(None, max_length=80)
    platz: Optional[str] = Field(None, max_length=40)
    lagerort: Optional[str] = Field(None, max_length=80)
    notiz: Optional[str] = Field(None, max_length=500)


class WerkzeugOut(_ORM):
    id: int
    code: str
    art: str
    art_text: str
    bezeichnung: str
    hersteller: Optional[str] = None
    artikelnummer: Optional[str] = None
    schneidstoff: Optional[str] = None
    durchmesser_mm: Optional[float] = None
    schneidenlaenge_mm: Optional[float] = None
    bohrung_schaft_mm: Optional[float] = None
    zaehnezahl: Optional[int] = None
    max_drehzahl: Optional[int] = None
    max_schaerfungen: Optional[int] = None
    kaufdatum: Optional[date] = None
    kaufpreis_cent: Optional[int] = None
    status: str
    status_text: str
    lagerort: Optional[str] = None
    maschine: Optional[str] = None
    platz: Optional[str] = None
    partner_code: Optional[str] = None
    notiz: Optional[str] = None
    einsatzgebiet: Optional[str] = None
    materialien: Optional[str] = None
    drehzahl_empfohlen: Optional[int] = None
    vorschub_empfohlen: Optional[float] = None
    parameter_notiz: Optional[str] = None
    masse_pruefen: bool = False
    anzahl_schaerfungen: int
    rest_schaerfungen: Optional[int] = None
    schaerfkosten_cent: int


class EreignisOut(_ORM):
    id: int
    zeitpunkt: datetime
    art: str
    text: str
    benutzer_name: Optional[str] = None


class SchaerfungOut(_ORM):
    id: int
    auftrag_id: int
    dienst: str
    abgabe_zeitpunkt: datetime
    zurueck_am: Optional[datetime] = None
    ergebnis: Optional[str] = None
    kosten_cent: Optional[int] = None
    notiz: Optional[str] = None


class WerkzeugDetail(WerkzeugOut):
    ereignisse: list[EreignisOut] = []
    schaerfpositionen: list[SchaerfungOut] = []


class PositionOut(_ORM):
    id: int
    werkzeug_id: int
    werkzeug_code: str
    werkzeug_bezeichnung: str
    werkzeug_art: str
    zurueck_am: Optional[datetime] = None
    ergebnis: Optional[str] = None
    kosten_cent: Optional[int] = None
    notiz: Optional[str] = None


class AuftragOut(_ORM):
    id: int
    dienst: str
    abgabe_zeitpunkt: datetime
    abgeschlossen_am: Optional[datetime] = None
    notiz: Optional[str] = None
    ist_offen: bool
    anzahl: int
    anzahl_zurueck: int
    kosten_cent: int
    positionen: list[PositionOut] = []


class AuftragEingabe(BaseModel):
    dienst: str = Field(..., min_length=1, max_length=120)
    werkzeug_ids: list[int] = Field(..., min_length=1, max_length=200)
    notiz: Optional[str] = Field(None, max_length=1000)


class RueckgabePosition(BaseModel):
    werkzeug_id: int
    ergebnis: str = ERGEBNIS_GESCHAERFT
    kosten_cent: Optional[int] = Field(None, ge=0, le=100_000_00)
    lagerort: Optional[str] = Field(None, max_length=80)
    notiz: Optional[str] = Field(None, max_length=500)
    # Nur Fräser/Bohrer: Maße nach dem Schärfen (freiwillig; ohne Angabe bleiben die alten stehen)
    neuer_durchmesser_mm: Optional[float] = Field(None, gt=0, le=2000)
    neue_laenge_mm: Optional[float] = Field(None, gt=0, le=2000)


class RueckgabeEingabe(BaseModel):
    positionen: list[RueckgabePosition] = Field(..., min_length=1)


# --------------------------------------------------------------------------------------
#  Helfer
# --------------------------------------------------------------------------------------

def _leer(wert: Optional[str]) -> Optional[str]:
    wert = (wert or "").strip()
    return wert or None


def _ereignis(db: Session, werkzeug: Schneidwerkzeug, benutzer: Optional[Benutzer], art: str, text: str) -> None:
    db.add(SchneidwerkzeugEreignis(
        werkzeug=werkzeug, benutzer_id=benutzer.id if benutzer else None, art=art, text=text,
    ))


def _lade(db: Session, werkzeug_id: int) -> Schneidwerkzeug:
    w = (
        db.query(Schneidwerkzeug)
        .options(
            selectinload(Schneidwerkzeug.schaerfpositionen).selectinload(SchaerfPosition.auftrag),
            selectinload(Schneidwerkzeug.ereignisse).selectinload(SchneidwerkzeugEreignis.benutzer),
            selectinload(Schneidwerkzeug.partner),
        )
        .filter(Schneidwerkzeug.id == werkzeug_id)
        .first()
    )
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Werkzeug nicht gefunden.")
    return w


def maschinen_liste(db: Session, nur_aktive: bool = True) -> list[WerkstattMaschine]:
    """Feste Maschinenliste; beim allerersten Zugriff mit den Vorgaben des Betriebs gefüllt."""
    if db.query(WerkstattMaschine).count() == 0:
        for i, name in enumerate(STANDARD_MASCHINEN):
            db.add(WerkstattMaschine(name=name, sortierung=i))
        db.commit()
    q = db.query(WerkstattMaschine)
    if nur_aktive:
        q = q.filter(WerkstattMaschine.aktiv.is_(True))
    return q.order_by(WerkstattMaschine.sortierung, WerkstattMaschine.name).all()


def naechster_code(db: Session, art: str) -> str:
    """Nächster freier Code der Art, dreistellig (SB-001, SB-002 …); Lücken bleiben."""
    praefix = ARTEN[art][1]
    hoechste = 0
    for (code,) in db.query(Schneidwerkzeug.code).filter(Schneidwerkzeug.code.like(f"{praefix}-%")):
        m = re.match(rf"^{praefix}-(\d+)$", code)
        if m:
            hoechste = max(hoechste, int(m.group(1)))
    return f"{praefix}-{hoechste + 1:03d}"


def _pruefe_art(art: str) -> str:
    if art not in ARTEN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannte Art. Erlaubt: {', '.join(ARTEN)}.")
    return art


def _partner(db: Session, code: Optional[str], selbst_id: Optional[int]) -> Optional[int]:
    code = (_leer(code) or "").upper()
    if not code:
        return None
    p = db.query(Schneidwerkzeug).filter(Schneidwerkzeug.code == code).first()
    if p is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Partner-Werkzeug {code} gibt es nicht.")
    if selbst_id is not None and p.id == selbst_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ein Werkzeug kann nicht sein eigener Partner sein.")
    return p.id


def _uebernehme(w: Schneidwerkzeug, e: WerkzeugEingabe) -> None:
    w.art = _pruefe_art(e.art)
    w.bezeichnung = e.bezeichnung.strip()
    w.hersteller = _leer(e.hersteller)
    w.artikelnummer = _leer(e.artikelnummer)
    w.schneidstoff = _leer(e.schneidstoff)
    w.durchmesser_mm = e.durchmesser_mm
    w.schneidenlaenge_mm = e.schneidenlaenge_mm
    w.bohrung_schaft_mm = e.bohrung_schaft_mm
    w.zaehnezahl = e.zaehnezahl
    w.max_drehzahl = e.max_drehzahl
    w.max_schaerfungen = e.max_schaerfungen
    w.kaufdatum = e.kaufdatum
    w.kaufpreis_cent = e.kaufpreis_cent
    w.lagerort = _leer(e.lagerort)
    w.notiz = _leer(e.notiz)
    w.einsatzgebiet = _leer(e.einsatzgebiet)
    # Materialien: kommagetrennt, ohne Doppelte, Reihenfolge wie eingegeben
    teile = list(dict.fromkeys(t.strip() for t in (e.materialien or "").split(",") if t.strip()))
    w.materialien = ", ".join(teile) or None
    w.drehzahl_empfohlen = e.drehzahl_empfohlen
    w.vorschub_empfohlen = e.vorschub_empfohlen
    w.parameter_notiz = _leer(e.parameter_notiz)


# --------------------------------------------------------------------------------------
#  Bestand
# --------------------------------------------------------------------------------------

@router.get("", response_model=list[WerkzeugOut])
def liste(
    suche: str = Query("", max_length=100),
    status_filter: str = Query("", alias="status", max_length=20),
    art: str = Query("", max_length=20),
    _: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Schneidwerkzeug]:
    """Bestand; ohne Status-Filter ohne Verschrottete (die zeigt nur status=verschrottet bzw. status=alle)."""
    q = db.query(Schneidwerkzeug).options(
        selectinload(Schneidwerkzeug.schaerfpositionen), selectinload(Schneidwerkzeug.partner),
    )
    if status_filter == "alle":
        pass
    elif status_filter:
        q = q.filter(Schneidwerkzeug.status == status_filter)
    else:
        q = q.filter(Schneidwerkzeug.status != STATUS_VERSCHROTTET)
    if art:
        q = q.filter(Schneidwerkzeug.art == art)
    s = suche.strip()
    if s:
        muster = f"%{s}%"
        q = q.filter(or_(
            Schneidwerkzeug.code.ilike(muster), Schneidwerkzeug.bezeichnung.ilike(muster),
            Schneidwerkzeug.hersteller.ilike(muster), Schneidwerkzeug.artikelnummer.ilike(muster),
            Schneidwerkzeug.maschine.ilike(muster), Schneidwerkzeug.lagerort.ilike(muster),
            Schneidwerkzeug.einsatzgebiet.ilike(muster), Schneidwerkzeug.materialien.ilike(muster),
        ))
    return q.order_by(Schneidwerkzeug.code).all()


@router.get("/stammwerte")
def stammwerte(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Auswahlwerte für Formulare: Arten, Status, Maschinenliste, Lagerorte, Schärfdienste, Materialien, nächste Codes."""
    def werte(spalte):
        return sorted({v for (v,) in db.query(spalte).distinct() if v}, key=str.lower)
    return {
        "arten": [{"key": k, "text": t, "praefix": p} for k, (t, p) in ARTEN.items()],
        "status": [{"key": k, "text": t} for k, t in STATUS.items()],
        "maschinen": [m.name for m in maschinen_liste(db)],
        "lagerorte": werte(Schneidwerkzeug.lagerort),
        # feste Schärfdienste zuerst, danach weitere, die schon einmal verwendet wurden
        "dienste": STANDARD_DIENSTE + [d for d in werte(SchaerfAuftrag.dienst) if d not in STANDARD_DIENSTE],
        "materialien": MATERIALIEN,
        "ergebnisse": [{"key": k, "text": t} for k, t in ERGEBNISSE.items()],
        "naechste_codes": {k: naechster_code(db, k) for k in ARTEN},
    }


@router.get("/uebersicht")
def uebersicht(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Zahlen je Status, Warnungen und die Verteilung nach Ort (je Maschine, je Lagerfach)."""
    alle = (
        db.query(Schneidwerkzeug).options(selectinload(Schneidwerkzeug.schaerfpositionen))
        .filter(Schneidwerkzeug.status != STATUS_VERSCHROTTET).order_by(Schneidwerkzeug.code).all()
    )
    kurz = lambda w: {"code": w.code, "bezeichnung": w.bezeichnung, "art_text": w.art_text, "platz": w.platz, "status": w.status}  # noqa: E731
    je_status = {k: 0 for k in STATUS if k != STATUS_VERSCHROTTET}
    gruppen: dict[tuple, dict] = {}
    in_maschine: dict[str, list] = {m.name: [] for m in maschinen_liste(db)}
    im_lager: dict[str, list] = {}
    for w in alle:
        je_status[w.status] = je_status.get(w.status, 0) + 1
        # Gleicher Typ = gleiche Artikelnummer (sonst gleiche Bezeichnung) innerhalb der Art.
        schluessel = (w.art, (w.artikelnummer or w.bezeichnung).strip().lower())
        g = gruppen.setdefault(schluessel, {"art_text": w.art_text, "bezeichnung": w.bezeichnung, "gesamt": 0, "lager": 0, "maschine": 0})
        g["gesamt"] += 1
        if w.status == STATUS_LAGER:
            g["lager"] += 1
            im_lager.setdefault(w.lagerort or "", []).append(kurz(w))
        if w.status == STATUS_MASCHINE:
            g["maschine"] += 1
            in_maschine.setdefault(w.maschine or "Ohne Maschine", []).append(kurz(w))
    ohne_ersatz = sorted(
        (g for g in gruppen.values() if g["maschine"] > 0 and g["lager"] == 0),
        key=lambda g: g["bezeichnung"].lower(),
    )
    # Schärfungen fast aufgebraucht: höchstens noch eine möglich.
    fast = [dict(kurz(w), rest=w.rest_schaerfungen) for w in alle if w.rest_schaerfungen is not None and w.rest_schaerfungen <= 1]
    offen = db.query(SchaerfAuftrag).filter(SchaerfAuftrag.abgeschlossen_am.is_(None)).count()
    teile = db.query(Verbrauchsteil).order_by(Verbrauchsteil.bezeichnung).all()
    return {
        "je_status": je_status, "gesamt": len(alle), "ohne_ersatz": ohne_ersatz, "offene_schaerfauftraege": offen,
        "fast_aufgebraucht": fast,
        "masse_pruefen": [kurz(w) for w in alle if w.masse_pruefen],
        "nachbestellen": [{"id": t.id, "bezeichnung": t.bezeichnung, "bestand": t.bestand, "mindestbestand": t.mindestbestand} for t in teile if t.unter_mindestbestand],
        "nach_ort": {
            "maschinen": [{"name": n, "werkzeuge": ws} for n, ws in in_maschine.items()],
            "lager": [{"name": n or "Ohne Fach", "werkzeuge": ws} for n, ws in sorted(im_lager.items(), key=lambda x: (x[0] == "", x[0].lower()))],
        },
    }


# ---- Maschinenliste (lesen: alle, ändern: Admin) ----

class MaschineEingabe(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    aktiv: bool = True


class MaschineOut(_ORM):
    id: int
    name: str
    aktiv: bool


@router.get("/maschinen", response_model=list[MaschineOut])
def maschinen(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WerkstattMaschine]:
    return maschinen_liste(db, nur_aktive=False)


@router.post("/maschinen", response_model=MaschineOut, status_code=status.HTTP_201_CREATED)
def maschine_anlegen(e: MaschineEingabe, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> WerkstattMaschine:
    name = e.name.strip()
    vorhandene = maschinen_liste(db, nur_aktive=False)
    if any(m.name.lower() == name.lower() for m in vorhandene):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Die Maschine „{name}“ gibt es schon.")
    m = WerkstattMaschine(name=name, aktiv=True, sortierung=max((x.sortierung for x in vorhandene), default=-1) + 1)
    db.add(m)
    db.commit()
    return m


@router.put("/maschinen/{maschine_id}", response_model=MaschineOut)
def maschine_aendern(maschine_id: int, e: MaschineEingabe, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> WerkstattMaschine:
    """Umbenennen zieht alle eingebauten Werkzeuge und zugeordneten Verbrauchsteile mit; Abschalten nur ohne eingebaute Werkzeuge."""
    m = next((x for x in maschinen_liste(db, nur_aktive=False) if x.id == maschine_id), None)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maschine nicht gefunden.")
    name = e.name.strip()
    if any(x.id != m.id and x.name.lower() == name.lower() for x in maschinen_liste(db, nur_aktive=False)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Die Maschine „{name}“ gibt es schon.")
    eingebaut = db.query(Schneidwerkzeug).filter(Schneidwerkzeug.maschine == m.name, Schneidwerkzeug.status == STATUS_MASCHINE).count()
    if not e.aktiv and eingebaut:
        raise HTTPException(status.HTTP_409_CONFLICT, f"In „{m.name}“ sind noch {eingebaut} Werkzeug(e) eingebaut. Bitte zuerst ausbauen.")
    if name != m.name:
        db.query(Schneidwerkzeug).filter(Schneidwerkzeug.maschine == m.name).update({"maschine": name})
        db.query(Verbrauchsteil).filter(Verbrauchsteil.maschine == m.name).update({"maschine": name})
        m.name = name
    m.aktiv = e.aktiv
    db.commit()
    return m


@router.get("/code/{code}", response_model=WerkzeugDetail)
def nach_code(code: str, _: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> Schneidwerkzeug:
    w = db.query(Schneidwerkzeug).filter(Schneidwerkzeug.code == code.strip().upper()).first()
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Werkzeug nicht gefunden.")
    return _lade(db, w.id)


@router.get("/{werkzeug_id}", response_model=WerkzeugDetail)
def detail(werkzeug_id: int, _: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> Schneidwerkzeug:
    return _lade(db, werkzeug_id)


@router.post("", response_model=WerkzeugDetail, status_code=status.HTTP_201_CREATED)
def anlegen(e: WerkzeugEingabe, admin: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Schneidwerkzeug:
    _pruefe_art(e.art)
    code = (_leer(e.code) or naechster_code(db, e.art)).upper()
    if not CODE_RE.match(code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code muss die Form XX-000 haben (z. B. SB-001).")
    if db.query(Schneidwerkzeug).filter(Schneidwerkzeug.code == code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Code {code} ist bereits vergeben.")
    w = Schneidwerkzeug(code=code, status=STATUS_LAGER)
    _uebernehme(w, e)
    w.partner_id = _partner(db, e.partner_code, None)
    db.add(w)
    _ereignis(db, w, admin, "angelegt", "Werkzeug angelegt.")
    db.commit()
    return _lade(db, w.id)


@router.put("/{werkzeug_id}", response_model=WerkzeugDetail)
def aendern(werkzeug_id: int, e: WerkzeugEingabe, admin: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Schneidwerkzeug:
    w = _lade(db, werkzeug_id)
    neuer_code = (_leer(e.code) or w.code).upper()
    if neuer_code != w.code:
        if not CODE_RE.match(neuer_code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code muss die Form XX-000 haben (z. B. SB-001).")
        if db.query(Schneidwerkzeug).filter(Schneidwerkzeug.code == neuer_code).first():
            raise HTTPException(status.HTTP_409_CONFLICT, f"Code {neuer_code} ist bereits vergeben.")
        w.code = neuer_code
    _uebernehme(w, e)
    w.partner_id = _partner(db, e.partner_code, w.id)
    _ereignis(db, w, admin, "geaendert", "Stammdaten geändert.")
    db.commit()
    return _lade(db, w.id)


@router.delete("/{werkzeug_id}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(werkzeug_id: int, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    """Löschen nur für Fehleingaben: sobald ein Werkzeug beim Schärfdienst war, bleibt es (dann verschrotten)."""
    w = _lade(db, werkzeug_id)
    if w.schaerfpositionen:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Das Werkzeug war schon beim Schärfdienst und bleibt für die Historie erhalten. Bitte stattdessen verschrotten.",
        )
    db.delete(w)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{werkzeug_id}/status", response_model=WerkzeugDetail)
def status_setzen(
    werkzeug_id: int, e: StatusEingabe,
    benutzer: Benutzer = Depends(get_current_user), db: Session = Depends(get_db),
) -> Schneidwerkzeug:
    """Statuswechsel: einbauen (maschine), ausbauen (lager), stumpf melden, sperren; verschrotten nur Admin."""
    w = _lade(db, werkzeug_id)
    ziel = e.status
    ist_admin = benutzer.rolle == Rolle.ADMIN
    if ziel not in STATUS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannter Status.")
    if ziel == STATUS_SCHAERFDIENST:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Zum Schärfdienst geht ein Werkzeug nur über einen Schärfauftrag.")
    if w.status == STATUS_SCHAERFDIENST:
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Werkzeug ist beim Schärfdienst. Bitte zuerst die Rückkehr im Schärfauftrag buchen.")
    if (ziel == STATUS_VERSCHROTTET or w.status == STATUS_VERSCHROTTET) and not ist_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verschrotten und Reaktivieren darf nur ein Admin.")

    if ziel == STATUS_MASCHINE:
        maschine = _leer(e.maschine)
        if not maschine:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte die Maschine angeben, in die das Werkzeug eingebaut wird.")
        erlaubt = {m.name.lower(): m.name for m in maschinen_liste(db)}
        if maschine.lower() not in erlaubt:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Die Maschine „{maschine}“ steht nicht in der Maschinenliste.")
        maschine = erlaubt[maschine.lower()]
        w.maschine, w.platz = maschine, _leer(e.platz)
        text = f"Eingebaut in {maschine}" + (f", Platz {w.platz}" if w.platz else "") + "."
    else:
        w.maschine, w.platz = None, None
        if _leer(e.lagerort):
            w.lagerort = _leer(e.lagerort)
        text = {
            STATUS_LAGER: "Ins Lager gelegt" + (f" ({w.lagerort})" if w.lagerort else "") + ".",
            STATUS_STUMPF: "Als stumpf gemeldet.",
            STATUS_GESPERRT: "Gesperrt.",
            STATUS_VERSCHROTTET: "Verschrottet.",
        }[ziel]
    notiz = _leer(e.notiz)
    if notiz:
        text += f" {notiz}"
    w.status = ziel
    _ereignis(db, w, benutzer, "status", text)
    db.commit()
    return _lade(db, w.id)


@router.post("/{werkzeug_id}/masse-geprueft", response_model=WerkzeugDetail)
def masse_geprueft(werkzeug_id: int, benutzer: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> Schneidwerkzeug:
    """Hakt den Hinweis „Maße an der CNC prüfen" ab (nach dem Schärfen von Fräsern und Bohrern)."""
    w = _lade(db, werkzeug_id)
    if w.masse_pruefen:
        w.masse_pruefen = False
        _ereignis(db, w, benutzer, "masse", "Maße an der CNC geprüft und eingetragen.")
        db.commit()
    return _lade(db, w.id)


@router.get("/{werkzeug_id}/qr-code")
def qr_code(werkzeug_id: int, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    w = _lade(db, werkzeug_id)
    return Response(
        content=qr.schneidwerkzeug_pdf(w), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="qr_{w.code}.pdf"'},
    )


# --------------------------------------------------------------------------------------
#  Schärfaufträge (nur Admin)
# --------------------------------------------------------------------------------------

def _lade_auftrag(db: Session, auftrag_id: int) -> SchaerfAuftrag:
    a = (
        db.query(SchaerfAuftrag)
        .options(selectinload(SchaerfAuftrag.positionen).selectinload(SchaerfPosition.werkzeug))
        .filter(SchaerfAuftrag.id == auftrag_id)
        .first()
    )
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schärfauftrag nicht gefunden.")
    return a


@schaerf_router.get("", response_model=list[AuftragOut])
def auftraege(
    offen: Optional[bool] = None, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db),
) -> list[SchaerfAuftrag]:
    q = db.query(SchaerfAuftrag).options(selectinload(SchaerfAuftrag.positionen).selectinload(SchaerfPosition.werkzeug))
    if offen is True:
        q = q.filter(SchaerfAuftrag.abgeschlossen_am.is_(None))
    elif offen is False:
        q = q.filter(SchaerfAuftrag.abgeschlossen_am.isnot(None))
    return q.order_by(SchaerfAuftrag.id.desc()).limit(200).all()


@schaerf_router.get("/{auftrag_id}", response_model=AuftragOut)
def auftrag(auftrag_id: int, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> SchaerfAuftrag:
    return _lade_auftrag(db, auftrag_id)


@schaerf_router.post("", response_model=AuftragOut, status_code=status.HTTP_201_CREATED)
def auftrag_anlegen(e: AuftragEingabe, admin: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> SchaerfAuftrag:
    """Gibt Werkzeuge an den Schärfdienst ab. Alles oder nichts: ein ungeeignetes Werkzeug bricht den Auftrag ab."""
    ids = list(dict.fromkeys(e.werkzeug_ids))
    werkzeuge = db.query(Schneidwerkzeug).filter(Schneidwerkzeug.id.in_(ids)).all()
    if len(werkzeuge) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mindestens ein Werkzeug gibt es nicht.")
    gesperrt = [w.code for w in werkzeuge if w.status in (STATUS_SCHAERFDIENST, STATUS_VERSCHROTTET)]
    if gesperrt:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Schon beim Schärfdienst oder verschrottet: {', '.join(sorted(gesperrt))}.")
    a = SchaerfAuftrag(dienst=e.dienst.strip(), notiz=_leer(e.notiz), erstellt_von_id=admin.id)
    db.add(a)
    for w in sorted(werkzeuge, key=lambda x: x.code):
        a.positionen.append(SchaerfPosition(werkzeug=w))
        w.status, w.maschine, w.platz = STATUS_SCHAERFDIENST, None, None
        _ereignis(db, w, admin, "schaerf_abgabe", f"An Schärfdienst {a.dienst} abgegeben.")
    db.commit()
    return _lade_auftrag(db, a.id)


@schaerf_router.post("/{auftrag_id}/rueckgabe", response_model=AuftragOut)
def rueckgabe(auftrag_id: int, e: RueckgabeEingabe, admin: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> SchaerfAuftrag:
    """Bucht die Rückkehr einzelner oder aller Werkzeuge eines Auftrags (Kosten, Ergebnis, Lagerort)."""
    a = _lade_auftrag(db, auftrag_id)
    offen = {p.werkzeug_id: p for p in a.positionen if p.zurueck_am is None}
    jetzt = datetime.now(timezone.utc)
    # Erst alles prüfen, dann buchen – eine fehlerhafte Zeile darf keine halbe Rückgabe hinterlassen.
    gesehen = set()
    for r in e.positionen:
        if r.werkzeug_id in gesehen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ein Werkzeug ist doppelt in der Rückgabe.")
        gesehen.add(r.werkzeug_id)
        if r.werkzeug_id not in offen:
            raise HTTPException(status.HTTP_409_CONFLICT, "Ein Werkzeug gehört nicht zu diesem Auftrag oder ist schon zurück.")
        if r.ergebnis not in ERGEBNISSE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ergebnis muss eines von {', '.join(ERGEBNISSE)} sein.")
    for r in e.positionen:
        p = offen[r.werkzeug_id]
        w = p.werkzeug
        p.zurueck_am, p.ergebnis, p.kosten_cent, p.notiz = jetzt, r.ergebnis, r.kosten_cent, _leer(r.notiz)
        kosten = f", {r.kosten_cent / 100:.2f} €".replace(".", ",") if r.kosten_cent is not None else ""
        if r.ergebnis == ERGEBNIS_AUSGEMUSTERT:
            w.status = STATUS_VERSCHROTTET
            _ereignis(db, w, admin, "schaerf_rueckgabe", f"Vom Schärfdienst {a.dienst} zurück, ausgemustert{kosten}.")
            continue
        w.status = STATUS_LAGER
        if _leer(r.lagerort):
            w.lagerort = _leer(r.lagerort)
        zusatz = ""
        if w.art in ARTEN_MIT_MASSPRUEFUNG:
            # Fräser/Bohrer sind nach dem Schärfen kleiner – die CNC braucht die neuen Maße.
            if r.neuer_durchmesser_mm is not None:
                w.durchmesser_mm = r.neuer_durchmesser_mm
                zusatz += f" Neuer Durchmesser {r.neuer_durchmesser_mm:g} mm.".replace(".", ",", 1) if "." in f"{r.neuer_durchmesser_mm:g}" else f" Neuer Durchmesser {r.neuer_durchmesser_mm:g} mm."
            if r.neue_laenge_mm is not None:
                w.schneidenlaenge_mm = r.neue_laenge_mm
                zusatz += f" Neue Länge {r.neue_laenge_mm:g} mm.".replace(".", ",", 1) if "." in f"{r.neue_laenge_mm:g}" else f" Neue Länge {r.neue_laenge_mm:g} mm."
            w.masse_pruefen = True
            zusatz += " Maße an der CNC prüfen."
        if r.ergebnis == ERGEBNIS_NEU_BESTUECKT:
            _ereignis(db, w, admin, "schaerf_rueckgabe", f"Vom Schärfdienst {a.dienst} zurück, neu bestückt{kosten}. Schärfzähler beginnt neu.{zusatz}")
        else:
            rest = w.rest_schaerfungen
            if rest is not None:
                zusatz = f" Noch {rest} Schärfung(en) möglich." + zusatz
            _ereignis(db, w, admin, "schaerf_rueckgabe", f"Vom Schärfdienst {a.dienst} zurück, geschärft{kosten}.{zusatz}")
    if all(p.zurueck_am is not None for p in a.positionen):
        a.abgeschlossen_am = jetzt
    db.commit()
    return _lade_auftrag(db, a.id)


# --------------------------------------------------------------------------------------
#  Verbrauchsteile (nur Stückzahl): lesen und Entnahme/Zugang alle, Stammdaten nur Admin
# --------------------------------------------------------------------------------------

class TeilEingabe(BaseModel):
    bezeichnung: str = Field(..., min_length=1, max_length=200)
    hersteller: Optional[str] = Field(None, max_length=120)
    artikelnummer: Optional[str] = Field(None, max_length=80)
    maschine: Optional[str] = Field(None, max_length=80)
    lagerort: Optional[str] = Field(None, max_length=80)
    mindestbestand: Optional[int] = Field(None, ge=0, le=100000)
    notiz: Optional[str] = Field(None, max_length=1000)
    bestand: Optional[int] = Field(None, ge=0, le=100000)  # nur beim Anlegen: Anfangsbestand


class BewegungEingabe(BaseModel):
    menge: int = Field(..., ge=-100000, le=100000)   # + Zugang, − Entnahme
    text: Optional[str] = Field(None, max_length=300)


class BewegungOut(_ORM):
    id: int
    zeitpunkt: datetime
    menge: int
    text: Optional[str] = None
    benutzer_name: Optional[str] = None


class TeilOut(_ORM):
    id: int
    bezeichnung: str
    hersteller: Optional[str] = None
    artikelnummer: Optional[str] = None
    maschine: Optional[str] = None
    lagerort: Optional[str] = None
    bestand: int
    mindestbestand: Optional[int] = None
    unter_mindestbestand: bool
    notiz: Optional[str] = None


class TeilDetail(TeilOut):
    bewegungen: list[BewegungOut] = []


def _lade_teil(db: Session, teil_id: int) -> Verbrauchsteil:
    t = (
        db.query(Verbrauchsteil)
        .options(selectinload(Verbrauchsteil.bewegungen).selectinload(VerbrauchsBewegung.benutzer))
        .filter(Verbrauchsteil.id == teil_id).first()
    )
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verbrauchsteil nicht gefunden.")
    return t


def _uebernehme_teil(t: Verbrauchsteil, e: TeilEingabe) -> None:
    t.bezeichnung = e.bezeichnung.strip()
    t.hersteller = _leer(e.hersteller)
    t.artikelnummer = _leer(e.artikelnummer)
    t.maschine = _leer(e.maschine)
    t.lagerort = _leer(e.lagerort)
    t.mindestbestand = e.mindestbestand
    t.notiz = _leer(e.notiz)


@verbrauch_router.get("", response_model=list[TeilOut])
def teile(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Verbrauchsteil]:
    return db.query(Verbrauchsteil).order_by(Verbrauchsteil.bezeichnung).all()


@verbrauch_router.get("/{teil_id}", response_model=TeilDetail)
def teil(teil_id: int, _: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> Verbrauchsteil:
    return _lade_teil(db, teil_id)


@verbrauch_router.post("", response_model=TeilDetail, status_code=status.HTTP_201_CREATED)
def teil_anlegen(e: TeilEingabe, admin: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Verbrauchsteil:
    t = Verbrauchsteil(bestand=e.bestand or 0)
    _uebernehme_teil(t, e)
    db.add(t)
    if t.bestand:
        t.bewegungen.append(VerbrauchsBewegung(benutzer_id=admin.id, menge=t.bestand, text="Anfangsbestand"))
    db.commit()
    return _lade_teil(db, t.id)


@verbrauch_router.put("/{teil_id}", response_model=TeilDetail)
def teil_aendern(teil_id: int, e: TeilEingabe, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Verbrauchsteil:
    """Ändert die Stammdaten. Der Bestand ändert sich nur über Bewegungen."""
    t = _lade_teil(db, teil_id)
    _uebernehme_teil(t, e)
    db.commit()
    return _lade_teil(db, t.id)


@verbrauch_router.delete("/{teil_id}", status_code=status.HTTP_204_NO_CONTENT)
def teil_loeschen(teil_id: int, _: Benutzer = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    db.delete(_lade_teil(db, teil_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@verbrauch_router.post("/{teil_id}/bewegung", response_model=TeilDetail)
def teil_bewegung(teil_id: int, e: BewegungEingabe, benutzer: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> Verbrauchsteil:
    """Entnahme (negativ) oder Zugang (positiv). Der Bestand kann nicht unter null fallen."""
    t = _lade_teil(db, teil_id)
    if e.menge == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Menge darf nicht 0 sein.")
    if t.bestand + e.menge < 0:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Es sind nur noch {t.bestand} Stück da.")
    t.bestand += e.menge
    t.bewegungen.append(VerbrauchsBewegung(benutzer_id=benutzer.id, menge=e.menge, text=_leer(e.text)))
    db.commit()
    return _lade_teil(db, t.id)
