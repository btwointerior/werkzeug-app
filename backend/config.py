"""
Konfiguration aus Umgebungsvariablen / .env-Datei.

Wird beim Import einmal initialisiert. Greife im restlichen Code via
`from backend.config import settings` darauf zu.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    # Kürzer als früher (war 30 Tage). Aktive Nutzer werden per Sliding-Refresh
    # nahtlos verlängert; inaktive müssen sich nach Ablauf neu anmelden.
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    # Token nur erneuern, wenn die Restlaufzeit unter dieser Schwelle liegt.
    TOKEN_REFRESH_SCHWELLE_SEKUNDEN: int = 2 * 24 * 3600  # 2 Tage
    DATEI_TOKEN_EXPIRE_SECONDS: int = 300  # 5 Minuten — gerade lang genug zum Rendern.

    # In QR-Codes eingebettete Basis-URL; muss nach außen erreichbar sein.
    BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

    # Erlaubte CORS-Origins. Standard: nur die eigene BASE_URL (Frontend wird
    # same-origin ausgeliefert). Kommagetrennt per Env überschreibbar.
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS", os.environ.get("BASE_URL", "http://localhost:8000")
        ).split(",")
        if o.strip()
    ]

    UPLOAD_DIR: Path = _PROJECT_ROOT / "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ERLAUBTE_BILD_TYPEN: set[str] = {"image/jpeg", "image/png", "image/webp"}
    ERLAUBTER_PDF_TYP: str = "application/pdf"

    def __init__(self) -> None:
        if not self.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY fehlt. Bitte .env-Datei mit SECRET_KEY=... anlegen "
                "(siehe .env.example)."
            )
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
