"""Freie Ausgabe: Kleinteile ohne Maschinen-Code (Schraubzwingen, Spritzen, …).

Beleg ist ein Pflicht-Foto plus Textbeschreibung. Rückgabe schließt den
Eintrag ab (kein Löschen — die Admin-Historie bleibt vollständig).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from backend.bilder import pruefe_bild_oder_400, speichere_verkleinert
from backend.dependencies import get_current_user
from backend.models import (
    Benutzer,
    ExternesTeam,
    FreieAusgabe,
    FreieAusgabeFoto,
    get_db,
)
from backend.schemas import FreieAusgabeOut, FreieAusgabeRueckgabeRequest
from backend.upload_urls import freie_ausgabe_zu_out

router = APIRouter(prefix="/api/freie-ausgaben", tags=["Freie Ausgabe"])

MAX_FOTOS = 3
MAX_BESCHREIBUNG = 500


def _lade(db: Session, ausgabe_id: int) -> FreieAusgabe:
    ausgabe = (
        db.query(FreieAusgabe)
        .options(selectinload(FreieAusgabe.fotos), selectinload(FreieAusgabe.benutzer))
        .filter(FreieAusgabe.id == ausgabe_id)
        .first()
    )
    if ausgabe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ausgabe nicht gefunden."
        )
    return ausgabe


@router.post("", response_model=FreieAusgabeOut, status_code=status.HTTP_201_CREATED)
async def freie_ausgabe_anlegen(
    beschreibung: str = Form(""),
    externes_team: Optional[str] = Form(None),
    dateien: list[UploadFile] = File(default=[]),
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FreieAusgabeOut:
    """Legt eine Ausgabe an: 1–3 Fotos (Pflicht), Beschreibung (Pflicht),
    optional externes Montageteam (find-or-create wie beim Maschinen-Ausleihen)."""
    text = (beschreibung or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte eine Beschreibung eingeben (was wird ausgegeben?).",
        )
    if len(text) > MAX_BESCHREIBUNG:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Beschreibung zu lang (max {MAX_BESCHREIBUNG} Zeichen).",
        )
    dateien = [d for d in dateien if d.filename]
    if not dateien:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mindestens ein Foto ist Pflicht.",
        )
    if len(dateien) > MAX_FOTOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximal {MAX_FOTOS} Fotos.",
        )

    bilder = []
    for datei in dateien:
        inhalt = await datei.read()
        bilder.append(pruefe_bild_oder_400(datei, inhalt))

    team_name = (externes_team or "").strip()
    team = None
    if team_name:
        team = db.query(ExternesTeam).filter(ExternesTeam.name == team_name).first()
        if team is None:
            team = ExternesTeam(name=team_name)
            db.add(team)
            db.flush()

    ausgabe = FreieAusgabe(
        benutzer_id=current_user.id,
        externes_team_id=team.id if team else None,
        beschreibung=text,
        ausgabe_zeitpunkt=datetime.now(timezone.utc),
    )
    db.add(ausgabe)
    db.flush()  # vergibt ausgabe.id für die Dateinamen

    for img in bilder:
        foto = FreieAusgabeFoto(ausgabe_id=ausgabe.id, datei_pfad="")
        db.add(foto)
        db.flush()
        foto.datei_pfad = f"ausgabe_{ausgabe.id}_foto_{foto.id}.jpg"
        speichere_verkleinert(img, foto.datei_pfad)

    db.commit()
    return freie_ausgabe_zu_out(_lade(db, ausgabe.id), current_user.id)


@router.get("/meine", response_model=list[FreieAusgabeOut])
def meine_freien_ausgaben(
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FreieAusgabeOut]:
    """Eigene offene Ausgaben (neueste zuerst)."""
    zeilen = (
        db.query(FreieAusgabe)
        .options(selectinload(FreieAusgabe.fotos), selectinload(FreieAusgabe.benutzer))
        .filter(
            FreieAusgabe.benutzer_id == current_user.id,
            FreieAusgabe.rueckgabe_zeitpunkt.is_(None),
        )
        .order_by(FreieAusgabe.ausgabe_zeitpunkt.desc())
        .all()
    )
    return [freie_ausgabe_zu_out(z, current_user.id) for z in zeilen]


@router.post("/{ausgabe_id}/zurueckgeben", response_model=FreieAusgabeOut)
def freie_ausgabe_zurueckgeben(
    ausgabe_id: int,
    daten: FreieAusgabeRueckgabeRequest | None = None,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FreieAusgabeOut:
    """Schließt die Ausgabe ab. Erlaubt für den Eigentümer und für Admins."""
    ausgabe = _lade(db, ausgabe_id)
    if ausgabe.benutzer_id != current_user.id and not current_user.ist_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur der Ausgebende oder ein Admin kann diese Ausgabe abschließen.",
        )
    if not ausgabe.ist_offen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diese Ausgabe ist bereits zurückgegeben.",
        )
    ausgabe.rueckgabe_zeitpunkt = datetime.now(timezone.utc)
    kommentar = (daten.kommentar if daten else None) or None
    ausgabe.rueckgabe_kommentar = kommentar.strip() if kommentar and kommentar.strip() else None
    db.commit()
    return freie_ausgabe_zu_out(_lade(db, ausgabe.id), current_user.id)
