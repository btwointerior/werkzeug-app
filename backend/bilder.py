"""Gemeinsame Bild-Helfer für Foto-Uploads (Maschinen-Galerie, Freie Ausgabe).

Validiert Typ/Größe/Magic-Bytes und verkleinert Bilder einheitlich auf
max. 1600 px (JPEG, Qualität 85), damit der Upload-Ordner nicht mit
Handy-Originalen volläuft.
"""

import io
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from backend.config import settings

MAX_KANTE_PX = 1600


def pruefe_bild_oder_400(datei: UploadFile, inhalt: bytes) -> Image.Image:
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


def speichere_verkleinert(img: Image.Image, dateiname: str) -> Path:
    """Verkleinert auf MAX_KANTE_PX und speichert als JPEG im Upload-Ordner."""
    img.thumbnail((MAX_KANTE_PX, MAX_KANTE_PX))
    if img.mode != "RGB":
        img = img.convert("RGB")
    ziel = settings.UPLOAD_DIR / dateiname
    img.save(ziel, "JPEG", quality=85, optimize=True)
    return ziel
