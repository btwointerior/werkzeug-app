"""Admin-Endpunkte: Maschinen-/Benutzer-Verwaltung, Uploads, QR-Codes, Statistiken."""

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status,
)
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend import anleitung_suche, ki_analyse, qr
from backend.config import settings
from backend.dependencies import require_admin
from backend.models import (
    Ausleihe,
    Benutzer,
    Maschine,
    MaschinenFoto,
    MaschinenStatus,
    Zubehoer,
    get_db,
)
from backend.schemas import (
    AusleiheHistorieOut,
    BenutzerCreate,
    BenutzerKurz,
    BenutzerOut,
    BenutzerUpdate,
    FotoAnalyseOut,
    MaschineCreate,
    MaschineKurz,
    MaschineOut,
    MaschineUpdate,
    SammeldruckRequest,
    StatistikenOut,
    TopMaschineEintrag,
    UeberfaelligeAusleiheEintrag,
)
from backend.upload_urls import maschine_zu_out

logger = logging.getLogger("werkzeug_app.admin")

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hole_maschine(db: Session, maschine_id: int) -> Maschine:
    m = db.query(Maschine).filter(Maschine.id == maschine_id).first()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden."
        )
    return m


def _loesche_datei(name: Optional[str]) -> None:
    if not name:
        return
    p = settings.UPLOAD_DIR / Path(name).name
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass  # nicht kritisch — Datei bleibt verwaist, Upload geht weiter


# ============================================================
#  Maschinen
# ============================================================

@router.get("/maschinen", response_model=list[MaschineOut])
def maschinen_liste(
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> list[MaschineOut]:
    """Listet alle Maschinen. Suche/Status-Filter erfolgen client-seitig
    (frontend/js/filter.js), daher keine Query-Parameter."""
    maschinen = (
        db.query(Maschine)
        .options(
            selectinload(Maschine.zubehoer_liste),
            selectinload(Maschine.ausleihen).selectinload(Ausleihe.benutzer),
            selectinload(Maschine.ausleihen).selectinload(
                Ausleihe.mitgenommenes_zubehoer
            ),
            selectinload(Maschine.ausleihen).selectinload(Ausleihe.externes_team),
        )
        .order_by(Maschine.maschinen_code)
        .all()
    )
    return [maschine_zu_out(m, current_user.id) for m in maschinen]


@router.post(
    "/maschinen", response_model=MaschineOut, status_code=status.HTTP_201_CREATED,
)
def maschine_anlegen(
    daten: MaschineCreate,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Legt eine neue Maschine an, inkl. Zubehör.

    Wirft 400, wenn der `maschinen_code` bereits vergeben ist.
    """
    if (
        db.query(Maschine)
        .filter(Maschine.maschinen_code == daten.maschinen_code)
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maschinen-Code '{daten.maschinen_code}' ist bereits vergeben.",
        )

    maschine = Maschine(
        maschinen_code=daten.maschinen_code,
        name=daten.name,
        platznummer=daten.platznummer,
        hersteller=daten.hersteller,
        seriennummer=daten.seriennummer,
        beschreibung=daten.beschreibung,
        foto_pfad=daten.foto_pfad,
        anleitung_pfad=daten.anleitung_pfad,
        status=daten.status,
    )
    for z in daten.zubehoer:
        maschine.zubehoer_liste.append(Zubehoer(bezeichnung=z.bezeichnung))
    db.add(maschine)
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.put("/maschinen/{maschine_id}", response_model=MaschineOut)
def maschine_bearbeiten(
    maschine_id: int,
    daten: MaschineUpdate,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Bearbeitet eine Maschine. Alle Felder optional.

    Wird `zubehoer` mitgesendet, wird die komplette Zubehörliste ersetzt.
    """
    maschine = _hole_maschine(db, maschine_id)
    update_data = daten.model_dump(exclude_unset=True)

    if "zubehoer" in update_data:
        maschine.zubehoer_liste.clear()
        for z in daten.zubehoer or []:
            maschine.zubehoer_liste.append(Zubehoer(bezeichnung=z.bezeichnung))
        update_data.pop("zubehoer")

    for feld, wert in update_data.items():
        setattr(maschine, feld, wert)

    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.delete("/maschinen/{maschine_id}", status_code=status.HTTP_204_NO_CONTENT)
def maschine_loeschen(maschine_id: int, db: Session = Depends(get_db)) -> None:
    """Löscht eine Maschine inkl. Foto und Anleitung.

    Verweigert, wenn eine offene Ausleihe existiert.
    """
    maschine = _hole_maschine(db, maschine_id)
    if maschine.aktuelle_ausleihe is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maschine hat eine offene Ausleihe und kann nicht gelöscht werden.",
        )
    _loesche_datei(maschine.foto_pfad)
    _loesche_datei(maschine.anleitung_pfad)
    for foto in maschine.fotos:
        if foto.datei_pfad != maschine.foto_pfad:
            _loesche_datei(foto.datei_pfad)
    db.delete(maschine)
    db.commit()


@router.post("/maschinen/{maschine_id}/freigeben", response_model=MaschineOut)
def maschine_freigeben(
    maschine_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Hebt den Status 'defekt' oder 'wartung' auf und setzt die Maschine auf 'verfuegbar'."""
    maschine = _hole_maschine(db, maschine_id)
    if maschine.status not in (MaschinenStatus.DEFEKT, MaschinenStatus.WARTUNG):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maschine ist nicht gesperrt.",
        )
    maschine.status = MaschinenStatus.VERFUEGBAR
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.get(
    "/maschinen/{maschine_id}/historie",
    response_model=list[AusleiheHistorieOut],
)
def maschine_historie(
    maschine_id: int, db: Session = Depends(get_db)
) -> list[Ausleihe]:
    """Liefert die komplette Ausleih-Historie einer Maschine (neueste zuerst)."""
    _hole_maschine(db, maschine_id)
    return (
        db.query(Ausleihe)
        .filter(Ausleihe.maschine_id == maschine_id)
        .order_by(Ausleihe.ausleih_zeitpunkt.desc())
        .all()
    )


# ============================================================
#  Fotos (Galerie: N Fotos je Maschine, eines ist Startbild)
# ============================================================

MAX_FOTOS_JE_UPLOAD = 10


def _pruefe_bild_oder_400(datei: UploadFile, inhalt: bytes) -> Image.Image:
    """Validiert Typ/Größe/Magic-Bytes und gibt das geöffnete Bild zurück."""
    if datei.content_type not in settings.ERLAUBTE_BILD_TYPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur JPG, PNG oder WebP erlaubt.",
        )
    if len(inhalt) > settings.MAX_UPLOAD_SIZE:
        mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Datei zu groß (max {mb} MB).",
        )
    try:
        Image.open(io.BytesIO(inhalt)).verify()
        return Image.open(io.BytesIO(inhalt))
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datei ist kein gültiges Bild.",
        )


def _foto_speichern(db: Session, maschine: Maschine, img: Image.Image) -> MaschinenFoto:
    """Verkleinert das Bild, legt Datei + MaschinenFoto-Zeile an (ohne Commit)."""
    img.thumbnail((1600, 1600))
    if img.mode != "RGB":
        img = img.convert("RGB")
    foto = MaschinenFoto(maschine_id=maschine.id, datei_pfad="")
    db.add(foto)
    db.flush()  # vergibt foto.id für den Dateinamen
    foto.datei_pfad = f"maschine_{maschine.id}_foto_{foto.id}.jpg"
    img.save(settings.UPLOAD_DIR / foto.datei_pfad, "JPEG", quality=85, optimize=True)
    return foto


def _setze_startbild(maschine: Maschine, start_foto: MaschinenFoto) -> None:
    for f in maschine.fotos:
        f.ist_start = f.id == start_foto.id
    maschine.foto_pfad = start_foto.datei_pfad


@router.post("/maschinen/{maschine_id}/fotos", response_model=MaschineOut)
async def fotos_hochladen(
    maschine_id: int,
    dateien: list[UploadFile] = File(...),
    start_index: int = Form(-1),
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Hängt 1-10 Fotos an die Maschine an (JPG/PNG/WebP, je max 10 MB).

    `start_index` (0-basiert, bezogen auf die mitgesendeten Dateien) legt das
    Startbild fest. Ohne Angabe wird das erste Foto Startbild, falls die
    Maschine noch keins hat.
    """
    maschine = _hole_maschine(db, maschine_id)
    if not dateien or len(dateien) > MAX_FOTOS_JE_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bitte 1 bis {MAX_FOTOS_JE_UPLOAD} Fotos hochladen.",
        )

    bilder = []
    for datei in dateien:
        inhalt = await datei.read()
        bilder.append(_pruefe_bild_oder_400(datei, inhalt))

    hatte_start = any(f.ist_start for f in maschine.fotos)
    neue = [_foto_speichern(db, maschine, img) for img in bilder]
    db.refresh(maschine)

    if 0 <= start_index < len(neue):
        _setze_startbild(maschine, neue[start_index])
    elif not hatte_start:
        _setze_startbild(maschine, neue[0])

    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.put("/maschinen/{maschine_id}/fotos/{foto_id}/start", response_model=MaschineOut)
def foto_als_start(
    maschine_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Legt das angegebene Foto als Startbild/Vorschaubild fest."""
    maschine = _hole_maschine(db, maschine_id)
    foto = next((f for f in maschine.fotos if f.id == foto_id), None)
    if foto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden."
        )
    _setze_startbild(maschine, foto)
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.delete("/maschinen/{maschine_id}/fotos/{foto_id}", response_model=MaschineOut)
def foto_loeschen(
    maschine_id: int,
    foto_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Löscht ein einzelnes Foto. War es das Startbild, rückt das nächste nach."""
    maschine = _hole_maschine(db, maschine_id)
    foto = next((f for f in maschine.fotos if f.id == foto_id), None)
    if foto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden."
        )
    war_start = foto.ist_start
    _loesche_datei(foto.datei_pfad)
    if maschine.foto_pfad == foto.datei_pfad:
        maschine.foto_pfad = None
    db.delete(foto)
    db.flush()
    db.refresh(maschine)
    if war_start and maschine.fotos:
        _setze_startbild(maschine, maschine.fotos[0])
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.post("/maschinen/{maschine_id}/foto", response_model=MaschineOut)
async def foto_hochladen(
    maschine_id: int,
    datei: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Alt-Endpunkt (eine Datei): hängt das Foto an und macht es zum Startbild."""
    maschine = _hole_maschine(db, maschine_id)
    inhalt = await datei.read()
    img = _pruefe_bild_oder_400(datei, inhalt)
    foto = _foto_speichern(db, maschine, img)
    db.refresh(maschine)
    _setze_startbild(maschine, foto)
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.delete(
    "/maschinen/{maschine_id}/foto",
    response_model=MaschineOut,
)
def foto_entfernen(
    maschine_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Alt-Endpunkt: entfernt das Startbild (nächstes Foto rückt nach)."""
    maschine = _hole_maschine(db, maschine_id)
    start = next((f for f in maschine.fotos if f.ist_start), None)
    if start is not None:
        return foto_loeschen(maschine_id, start.id, db, current_user)
    # Alt-Datenbestand ohne Galerie-Zeilen: nur foto_pfad leeren.
    _loesche_datei(maschine.foto_pfad)
    maschine.foto_pfad = None
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


MAX_ANALYSE_FOTOS = 5


@router.post("/maschinen/foto-analyse", response_model=FotoAnalyseOut)
async def foto_analyse(dateien: list[UploadFile] = File(...)) -> FotoAnalyseOut:
    """Liest Typenschild-Fotos per KI aus (Vorschlag für Neu-Anlage).

    Nimmt 1-5 Bilder (JPG/PNG/WebP, je max 10 MB), verkleinert sie und lässt
    Claude (Bedrock) Name/Hersteller/Seriennummer vorschlagen. Legt NICHTS an -
    reiner Vorschlags-Endpunkt.
    """
    if not ki_analyse.ist_konfiguriert():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KI-Analyse ist auf diesem Server nicht konfiguriert.",
        )
    if not dateien or len(dateien) > MAX_ANALYSE_FOTOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bitte 1 bis {MAX_ANALYSE_FOTOS} Fotos hochladen.",
        )

    bilder: list[bytes] = []
    for datei in dateien:
        if datei.content_type not in settings.ERLAUBTE_BILD_TYPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nur JPG, PNG oder WebP erlaubt.",
            )
        inhalt = await datei.read()
        if len(inhalt) > settings.MAX_UPLOAD_SIZE:
            mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Datei zu groß (max {mb} MB).",
            )
        try:
            Image.open(io.BytesIO(inhalt)).verify()
            img = Image.open(io.BytesIO(inhalt))
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mindestens eine Datei ist kein gültiges Bild.",
            )
        img.thumbnail((1568, 1568))
        if img.mode != "RGB":
            img = img.convert("RGB")
        puffer = io.BytesIO()
        img.save(puffer, "JPEG", quality=85, optimize=True)
        bilder.append(puffer.getvalue())

    try:
        ergebnis = ki_analyse.analysiere_fotos(bilder)
    except ki_analyse.KIAnalyseFehler as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    return FotoAnalyseOut(**ergebnis)


# ============================================================
#  Anleitung-Upload (PDF)
# ============================================================

@router.post("/maschinen/{maschine_id}/anleitung", response_model=MaschineOut)
async def anleitung_hochladen(
    maschine_id: int,
    datei: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Lädt eine Betriebsanleitung (PDF, max 10 MB) hoch und ersetzt die alte."""
    maschine = _hole_maschine(db, maschine_id)

    if datei.content_type != settings.ERLAUBTER_PDF_TYP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur PDF-Dateien erlaubt.",
        )

    inhalt = await datei.read()
    if len(inhalt) > settings.MAX_UPLOAD_SIZE:
        mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Datei zu groß (max {mb} MB).",
        )

    # Magic-Bytes-Check: PDFs starten mit "%PDF-"
    if not inhalt[:5] == b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datei ist kein gültiges PDF.",
        )

    neuer_name = f"maschine_{maschine_id}_anleitung.pdf"
    ziel = settings.UPLOAD_DIR / neuer_name
    ziel.write_bytes(inhalt)

    if maschine.anleitung_pfad and maschine.anleitung_pfad != neuer_name:
        _loesche_datei(maschine.anleitung_pfad)

    maschine.anleitung_pfad = neuer_name
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.post("/maschinen/{maschine_id}/anleitung-suche", response_model=MaschineOut)
def anleitung_suchen(
    maschine_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Sucht die Bedienungsanleitung (PDF) automatisch im Internet.

    Nutzt Hersteller + Name der Maschine als Suchbegriffe; zu große PDFs werden
    per Ghostscript verkleinert. Ersetzt eine ggf. vorhandene Anleitung.
    """
    maschine = _hole_maschine(db, maschine_id)
    if not (maschine.hersteller or "").strip() or not (maschine.name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Für die Suche müssen Hersteller und Name gepflegt sein.",
        )
    try:
        inhalt, quelle = anleitung_suche.suche_anleitung(maschine.hersteller, maschine.name)
    except anleitung_suche.AnleitungNichtGefunden as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    neuer_name = f"maschine_{maschine_id}_anleitung.pdf"
    (settings.UPLOAD_DIR / neuer_name).write_bytes(inhalt)
    if maschine.anleitung_pfad and maschine.anleitung_pfad != neuer_name:
        _loesche_datei(maschine.anleitung_pfad)
    maschine.anleitung_pfad = neuer_name
    logger.info("Anleitung fuer Maschine %s aus %s uebernommen (%d Bytes)",
                maschine.maschinen_code, quelle, len(inhalt))
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


@router.delete("/maschinen/{maschine_id}/anleitung", response_model=MaschineOut)
def anleitung_entfernen(
    maschine_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> MaschineOut:
    """Entfernt die Betriebsanleitung (Datei + DB-Pfad)."""
    maschine = _hole_maschine(db, maschine_id)
    _loesche_datei(maschine.anleitung_pfad)
    maschine.anleitung_pfad = None
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)


# ============================================================
#  QR-Codes
# ============================================================

@router.get("/maschinen/{maschine_id}/qr-code")
def qr_einzel(maschine_id: int, db: Session = Depends(get_db)) -> Response:
    """Liefert ein A6-PDF mit dem QR-Etikett der Maschine (Inline-Ansicht im Browser)."""
    maschine = _hole_maschine(db, maschine_id)
    pdf = qr.einzel_pdf(maschine)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'inline; filename="qr_{maschine.maschinen_code}.pdf"',
        },
    )


@router.post("/qr-codes/sammeldruck")
def qr_sammel(
    daten: SammeldruckRequest, db: Session = Depends(get_db)
) -> Response:
    """A4-PDF mit bis zu 4 Etiketten pro Seite (2×2) inkl. Schnittlinien."""
    eindeutige_ids = list(dict.fromkeys(daten.maschine_ids))  # behalte Reihenfolge
    maschinen = (
        db.query(Maschine).filter(Maschine.id.in_(eindeutige_ids)).all()
    )
    if len(maschinen) != len(eindeutige_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eine oder mehrere Maschinen-IDs existieren nicht.",
        )
    by_id = {m.id: m for m in maschinen}
    sortiert = [by_id[i] for i in eindeutige_ids]

    pdf = qr.sammel_pdf(sortiert)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="qr_sammeldruck.pdf"',
        },
    )


# ============================================================
#  Benutzer
# ============================================================

@router.get("/benutzer", response_model=list[BenutzerOut])
def benutzer_liste(db: Session = Depends(get_db)) -> list[Benutzer]:
    """Listet alle Benutzer (aktiv und gesperrt)."""
    return db.query(Benutzer).order_by(Benutzer.benutzername).all()


@router.post(
    "/benutzer", response_model=BenutzerOut, status_code=status.HTTP_201_CREATED,
)
def benutzer_anlegen(
    daten: BenutzerCreate, db: Session = Depends(get_db)
) -> Benutzer:
    """Legt einen neuen Benutzer an. 400 wenn der Benutzername bereits vergeben ist."""
    if (
        db.query(Benutzer)
        .filter(Benutzer.benutzername == daten.benutzername)
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Benutzername '{daten.benutzername}' ist bereits vergeben.",
        )
    benutzer = Benutzer(
        benutzername=daten.benutzername,
        vorname=daten.vorname,
        nachname=daten.nachname,
        rolle=daten.rolle,
        email=daten.email,
    )
    benutzer.setze_passwort(daten.passwort)
    db.add(benutzer)
    db.commit()
    db.refresh(benutzer)
    return benutzer


@router.put("/benutzer/{benutzer_id}", response_model=BenutzerOut)
def benutzer_bearbeiten(
    benutzer_id: int,
    daten: BenutzerUpdate,
    db: Session = Depends(get_db),
) -> Benutzer:
    """Bearbeitet einen Benutzer (auch zum Sperren via `aktiv=false` oder Passwort-Reset)."""
    benutzer = db.query(Benutzer).filter(Benutzer.id == benutzer_id).first()
    if benutzer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden."
        )
    update_data = daten.model_dump(exclude_unset=True)
    neues_passwort = update_data.pop("neues_passwort", None)
    for feld, wert in update_data.items():
        setattr(benutzer, feld, wert)
    if neues_passwort:
        benutzer.setze_passwort(neues_passwort)
    db.commit()
    db.refresh(benutzer)
    return benutzer


@router.delete("/benutzer/{benutzer_id}", status_code=status.HTTP_204_NO_CONTENT)
def benutzer_loeschen(
    benutzer_id: int,
    db: Session = Depends(get_db),
    current_user: Benutzer = Depends(require_admin),
) -> None:
    """Löscht einen Mitarbeiter endgültig (Hard-Delete).

    Der System-Administrator darf einen Benutzer auch dann endgültig löschen,
    wenn bereits abgeschlossene Ausleih-Historie vorhanden ist – diese wird dabei
    mitgelöscht. Blockiert wird nur, wenn der Benutzer noch eine *offene* Ausleihe
    hat (Maschine aktuell ausgeliehen); dann muss zuerst die Rückgabe gebucht
    werden. Selbst-Löschen ist verboten.
    """
    benutzer = db.query(Benutzer).filter(Benutzer.id == benutzer_id).first()
    if benutzer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden."
        )
    if benutzer.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sie können sich nicht selbst löschen.",
        )
    hat_offene_ausleihe = (
        db.query(Ausleihe)
        .filter(
            Ausleihe.benutzer_id == benutzer.id,
            Ausleihe.rueckgabe_zeitpunkt.is_(None),
        )
        .first()
    )
    if hat_offene_ausleihe is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Mitarbeiter hat noch eine offene Ausleihe und kann nicht gelöscht "
                "werden. Bitte zuerst die Rückgabe der Maschine(n) buchen."
            ),
        )
    # Hard-Delete: abgeschlossene Ausleih-Historie des Benutzers mitlöschen
    # (AusleiheZubehoer hängt per Cascade an Ausleihe und wird mitentfernt).
    for ausleihe in (
        db.query(Ausleihe).filter(Ausleihe.benutzer_id == benutzer.id).all()
    ):
        db.delete(ausleihe)
    db.delete(benutzer)
    db.commit()


# ============================================================
#  Statistiken
# ============================================================

@router.get("/statistiken", response_model=StatistikenOut)
def statistiken(db: Session = Depends(get_db)) -> StatistikenOut:
    """Top-10 meistgenutzte Maschinen + offene Ausleihen, die älter als 7 Tage sind."""
    top = (
        db.query(Maschine, func.count(Ausleihe.id).label("anz"))
        .outerjoin(Ausleihe, Ausleihe.maschine_id == Maschine.id)
        .group_by(Maschine.id)
        .order_by(func.count(Ausleihe.id).desc(), Maschine.maschinen_code)
        .limit(10)
        .all()
    )
    top_maschinen = [
        TopMaschineEintrag(
            id=m.id,
            maschinen_code=m.maschinen_code,
            name=m.name,
            anzahl_ausleihen=int(anz),
        )
        for m, anz in top
    ]

    cutoff = _now_naive() - timedelta(days=7)
    offene = (
        db.query(Ausleihe)
        .filter(
            Ausleihe.rueckgabe_zeitpunkt.is_(None),
            Ausleihe.ausleih_zeitpunkt < cutoff,
        )
        .order_by(Ausleihe.ausleih_zeitpunkt.asc())
        .all()
    )
    ueberfaellige = [
        UeberfaelligeAusleiheEintrag(
            id=a.id,
            maschine=MaschineKurz.model_validate(a.maschine),
            benutzer=BenutzerKurz.model_validate(a.benutzer),
            ausleih_zeitpunkt=a.ausleih_zeitpunkt,
            dauer_tage=a.dauer_tage,
        )
        for a in offene
    ]
    return StatistikenOut(
        top_maschinen=top_maschinen, ueberfaellige=ueberfaellige
    )
