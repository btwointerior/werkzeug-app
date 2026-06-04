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
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    DATEI_TOKEN_EXPIRE_SECONDS: int = 300  # 5 Minuten — gerade lang genug zum Rendern.

    # In QR-Codes eingebettete Basis-URL; muss nach außen erreichbar sein.
    BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

    CORS_ORIGINS: list[str] = ["*"]

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
