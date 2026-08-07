"""Helfer, der `MaschineOut` mit fertigen Upload-URLs (inkl. Datei-Token) anreichert.

Wird in jedem Router-Endpunkt aufgerufen, der eine `MaschineOut` zurückgibt,
damit das Frontend die URLs direkt verwenden kann.
"""

from backend.auth import create_datei_token
from backend.models import Maschine
from backend.schemas import MaschineOut


def maschine_zu_out(maschine: Maschine, benutzer_id: int) -> MaschineOut:
    """Erzeugt ein `MaschineOut` aus dem ORM-Objekt + füllt die Upload-URLs."""
    out = MaschineOut.model_validate(maschine)
    if maschine.foto_pfad:
        token = create_datei_token(benutzer_id, maschine.foto_pfad)
        out.foto_url = f"/uploads/{maschine.foto_pfad}?t={token}"
    if maschine.anleitung_pfad:
        token = create_datei_token(benutzer_id, maschine.anleitung_pfad)
        out.anleitung_url = f"/uploads/{maschine.anleitung_pfad}?t={token}"
    for foto_out, foto in zip(out.fotos, maschine.fotos):
        token = create_datei_token(benutzer_id, foto.datei_pfad)
        foto_out.url = f"/uploads/{foto.datei_pfad}?t={token}"
    return out
