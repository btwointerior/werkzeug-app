"""Mitarbeiter-Endpunkte rund um Maschinen: Lookup, Ausleihen, Zurückgeben."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user
from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Benutzer,
    Maschine,
    MaschinenStatus,
    Rolle,
    RueckgabeZustand,
    get_db,
)
from backend.schemas import (
    AusleihenRequest,
    MaschineOut,
    MeineAusleiheOut,
    ZurueckgabeRequest,
)
from backend.upload_urls import maschine_zu_out

router = APIRouter(prefix="/api/maschinen", tags=["Maschinen"])


@router.get("/meine", response_model=list[MeineAusleiheOut])
def meine_ausleihen(
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Ausleihe]:
    """Liefert alle aktuell offenen Ausleihen des angemeldeten Mitarbeiters."""
    return (
        db.query(Ausleihe)
        .filter(
            Ausleihe.benutzer_id == current_user.id,
            Ausleihe.rueckgabe_zeitpunkt.is_(None),
        )
        .order_by(Ausleihe.ausleih_zeitpunkt.desc())
        .all()
    )


@router.get("/by-code/{maschinen_code}", response_model=MaschineOut)
def maschine_per_code(
    maschinen_code: str,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaschineOut:
    """Sucht eine Maschine anhand ihres QR-Codes (z.B. 'M-0042')."""
    maschine = (
        db.query(Maschine).filter(Maschine.maschinen_code == maschinen_code).first()
    )
    if maschine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Maschine mit Code '{maschinen_code}' gefunden.",
        )
    return maschine_zu_out(maschine, current_user.id)


@router.post("/{maschine_id}/ausleihen", response_model=MaschineOut)
def maschine_ausleihen(
    maschine_id: int,
    daten: AusleihenRequest | None = None,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaschineOut:
    """Übernimmt eine Maschine in die eigene Ausleihe.

    Voraussetzungen: Maschine existiert und hat Status 'verfuegbar'.
    Optional wird das mitgenommene Zubehör protokolliert.
    """
    maschine = db.query(Maschine).filter(Maschine.id == maschine_id).first()
    if maschine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maschine nicht gefunden.",
        )

    if maschine.status != MaschinenStatus.VERFUEGBAR:
        meldungen = {
            MaschinenStatus.AUSGELIEHEN: "Maschine ist bereits ausgeliehen.",
            MaschinenStatus.DEFEKT: "Maschine ist als defekt gemeldet und muss vom Admin freigegeben werden.",
            MaschinenStatus.WARTUNG: "Maschine ist in Wartung und muss vom Admin freigegeben werden.",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=meldungen.get(maschine.status, "Maschine ist nicht verfügbar."),
        )

    bezeichnungen = daten.zubehoer_bezeichnungen if daten else []
    gueltige = {z.bezeichnung for z in maschine.zubehoer_liste}
    ungueltig = [b for b in bezeichnungen if b not in gueltige]
    if ungueltig:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unbekanntes Zubehör: {', '.join(ungueltig)}",
        )

    neue_ausleihe = Ausleihe(
        maschine_id=maschine.id,
        benutzer_id=current_user.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
    )
    for bezeichnung in bezeichnungen:
        neue_ausleihe.mitgenommenes_zubehoer.append(
            AusleiheZubehoer(bezeichnung=bezeichnung)
        )
    maschine.status = MaschinenStatus.AUSGELIEHEN
    db.add(neue_ausleihe)
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.post("/{maschine_id}/zurueckgeben", response_model=MaschineOut)
def maschine_zurueckgeben(
    maschine_id: int,
    daten: ZurueckgabeRequest,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaschineOut:
    """Gibt eine Maschine zurück.

    Nur die Person, die die Maschine ausgeliehen hat (oder ein Admin), darf
    zurückgeben. Der neue Maschinen-Status leitet sich vom Rückgabe-Zustand ab:
    `ok` → verfuegbar, `defekt` → defekt, `wartung` → wartung.
    """
    maschine = db.query(Maschine).filter(Maschine.id == maschine_id).first()
    if maschine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maschine nicht gefunden.",
        )

    offene_ausleihe = maschine.aktuelle_ausleihe
    if offene_ausleihe is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Für diese Maschine gibt es keine offene Ausleihe.",
        )

    if (
        offene_ausleihe.benutzer_id != current_user.id
        and current_user.rolle != Rolle.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur die Person, die die Maschine ausgeliehen hat, oder ein Admin "
            "darf sie zurückgeben.",
        )

    offene_ausleihe.rueckgabe_zeitpunkt = datetime.now(timezone.utc)
    offene_ausleihe.rueckgabe_zustand = daten.zustand

    kommentar = daten.kommentar
    if daten.zurueckgebrachte_zubehoer_ids is None:
        # Abwärtskompatibel: ohne Angabe gilt alles als zurückgebracht.
        for zeile in offene_ausleihe.mitgenommenes_zubehoer:
            zeile.zurueckgebracht = True
    else:
        zurueck_ids = set(daten.zurueckgebrachte_zubehoer_ids)
        fehlend = [
            zeile.bezeichnung
            for zeile in offene_ausleihe.mitgenommenes_zubehoer
            if zeile.id not in zurueck_ids
        ]
        if fehlend and not (kommentar and kommentar.strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bei fehlendem Zubehör ist ein Kommentar erforderlich.",
            )
        for zeile in offene_ausleihe.mitgenommenes_zubehoer:
            zeile.zurueckgebracht = zeile.id in zurueck_ids
        if fehlend:
            vermerk = "⚠ Nicht zurückgegeben: " + ", ".join(fehlend)
            kommentar = f"{kommentar}\n{vermerk}" if kommentar else vermerk
    offene_ausleihe.rueckgabe_kommentar = kommentar

    neuer_status = {
        RueckgabeZustand.OK: MaschinenStatus.VERFUEGBAR,
        RueckgabeZustand.DEFEKT: MaschinenStatus.DEFEKT,
        RueckgabeZustand.WARTUNG_NOETIG: MaschinenStatus.WARTUNG,
    }[daten.zustand]
    maschine.status = neuer_status

    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)
