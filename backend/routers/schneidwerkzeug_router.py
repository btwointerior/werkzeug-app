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
    ARTEN, ERGEBNIS_AUSGEMUSTERT, ERGEBNIS_GESCHAERFT, STATUS, STATUS_GESPERRT, STATUS_LAGER,
    STATUS_MASCHINE, STATUS_SCHAERFDIENST, STATUS_STUMPF, STATUS_VERSCHROTTET,
    SchaerfAuftrag, SchaerfPosition, Schneidwerkzeug, SchneidwerkzeugEreignis,
)

router = APIRouter(prefix="/api/schneidwerkzeuge", tags=["Schneidwerkzeuge"])
schaerf_router = APIRouter(prefix="/api/schaerfauftraege", tags=["Schärfaufträge"])

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
        ))
    return q.order_by(Schneidwerkzeug.code).all()


@router.get("/stammwerte")
def stammwerte(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Auswahlwerte für Formulare: Arten, Status, bisher verwendete Maschinen/Lagerorte/Dienste, nächste Codes."""
    def werte(spalte):
        return sorted({v for (v,) in db.query(spalte).distinct() if v}, key=str.lower)
    return {
        "arten": [{"key": k, "text": t, "praefix": p} for k, (t, p) in ARTEN.items()],
        "status": [{"key": k, "text": t} for k, t in STATUS.items()],
        "maschinen": werte(Schneidwerkzeug.maschine),
        "lagerorte": werte(Schneidwerkzeug.lagerort),
        "dienste": werte(SchaerfAuftrag.dienst),
        "naechste_codes": {k: naechster_code(db, k) for k in ARTEN},
    }


@router.get("/uebersicht")
def uebersicht(_: Benutzer = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Zahlen je Status und Typen, für die kein scharfes Ersatzwerkzeug im Lager liegt."""
    alle = db.query(Schneidwerkzeug).filter(Schneidwerkzeug.status != STATUS_VERSCHROTTET).all()
    je_status = {k: 0 for k in STATUS if k != STATUS_VERSCHROTTET}
    gruppen: dict[tuple, dict] = {}
    for w in alle:
        je_status[w.status] = je_status.get(w.status, 0) + 1
        # Gleicher Typ = gleiche Artikelnummer (sonst gleiche Bezeichnung) innerhalb der Art.
        schluessel = (w.art, (w.artikelnummer or w.bezeichnung).strip().lower())
        g = gruppen.setdefault(schluessel, {"art_text": w.art_text, "bezeichnung": w.bezeichnung, "gesamt": 0, "lager": 0, "maschine": 0})
        g["gesamt"] += 1
        if w.status == STATUS_LAGER:
            g["lager"] += 1
        if w.status == STATUS_MASCHINE:
            g["maschine"] += 1
    ohne_ersatz = sorted(
        (g for g in gruppen.values() if g["maschine"] > 0 and g["lager"] == 0),
        key=lambda g: g["bezeichnung"].lower(),
    )
    offen = db.query(SchaerfAuftrag).filter(SchaerfAuftrag.abgeschlossen_am.is_(None)).count()
    return {"je_status": je_status, "gesamt": len(alle), "ohne_ersatz": ohne_ersatz, "offene_schaerfauftraege": offen}


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
        if r.ergebnis not in (ERGEBNIS_GESCHAERFT, ERGEBNIS_AUSGEMUSTERT):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ergebnis muss „geschaerft“ oder „ausgemustert“ sein.")
    for r in e.positionen:
        p = offen[r.werkzeug_id]
        w = p.werkzeug
        p.zurueck_am, p.ergebnis, p.kosten_cent, p.notiz = jetzt, r.ergebnis, r.kosten_cent, _leer(r.notiz)
        kosten = f", {r.kosten_cent / 100:.2f} €".replace(".", ",") if r.kosten_cent is not None else ""
        if r.ergebnis == ERGEBNIS_GESCHAERFT:
            w.status = STATUS_LAGER
            if _leer(r.lagerort):
                w.lagerort = _leer(r.lagerort)
            rest = w.rest_schaerfungen
            zusatz = f" Noch {rest} Schärfung(en) möglich." if rest is not None else ""
            _ereignis(db, w, admin, "schaerf_rueckgabe", f"Vom Schärfdienst {a.dienst} zurück, geschärft{kosten}.{zusatz}")
        else:
            w.status = STATUS_VERSCHROTTET
            _ereignis(db, w, admin, "schaerf_rueckgabe", f"Vom Schärfdienst {a.dienst} zurück, ausgemustert{kosten}.")
    if all(p.zurueck_am is not None for p in a.positionen):
        a.abgeschlossen_am = jetzt
    db.commit()
    return _lade_auftrag(db, a.id)
