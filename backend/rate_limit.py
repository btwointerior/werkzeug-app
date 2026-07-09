"""Schlanker In-Memory-Brute-Force-Schutz für den Login (ohne Zusatz-Abhängigkeit).

Zählt fehlgeschlagene Login-Versuche pro (IP + Benutzername) innerhalb eines
Zeitfensters. Nach zu vielen Fehlversuchen wird weiter geblockt (HTTP 429), bis
das Fenster abläuft. Ein erfolgreicher Login setzt den Zähler zurück.

Hinweis: der Zustand lebt im Prozessspeicher. Für den aktuellen Single-Worker-
Betrieb ausreichend; bei mehreren Workern bräuchte es einen gemeinsamen Store.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, status

MAX_FEHLVERSUCHE = 5
FENSTER_SEKUNDEN = 300  # 5 Minuten

_versuche: dict[str, list[float]] = defaultdict(list)


def _aktuelle_versuche(key: str, jetzt: float) -> list[float]:
    frisch = [t for t in _versuche[key] if jetzt - t < FENSTER_SEKUNDEN]
    _versuche[key] = frisch
    return frisch


def pruefe(key: str) -> None:
    """Blockt mit 429, wenn im Fenster bereits zu viele Fehlversuche vorliegen."""
    if len(_aktuelle_versuche(key, time.monotonic())) >= MAX_FEHLVERSUCHE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Fehlversuche. Bitte einige Minuten warten und erneut versuchen.",
        )


def merke_fehlversuch(key: str) -> None:
    _versuche[key].append(time.monotonic())


def reset(key: str) -> None:
    _versuche.pop(key, None)


def _reset_all() -> None:
    """Nur für Tests: kompletten Zustand leeren."""
    _versuche.clear()
