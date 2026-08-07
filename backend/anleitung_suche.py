"""Automatische Websuche nach der Bedienungsanleitung (PDF) einer Maschine.

Ablauf: DuckDuckGo-HTML-Suche nach "<Hersteller> <Name> Betriebsanleitung
filetype:pdf" -> Kandidaten-URLs (Hersteller-Domain bevorzugt) -> Download mit
Größenlimit -> PDF-Prüfung (Magic Bytes) -> bei Übergröße Verkleinerung per
Ghostscript. Nur Standardbibliothek + optional gs auf dem Server.
"""

import gzip
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("werkzeug_app.anleitung_suche")

MAX_PDF_BYTES = 10 * 1024 * 1024      # Ziel: bestehendes Upload-Limit der App
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024  # harte Abbruchgrenze beim Laden
MAX_KANDIDATEN = 6
TIMEOUT = 20
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36")


class AnleitungNichtGefunden(Exception):
    """Keine brauchbare PDF-Anleitung gefunden/ladbar."""


def _hole(url: str, max_bytes: int) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA, "Accept-Encoding": "gzip",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as antwort:
        daten = antwort.read(max_bytes + 1)
    if len(daten) > max_bytes:
        raise AnleitungNichtGefunden("Datei zu groß.")
    if daten[:2] == b"\x1f\x8b":  # gzip
        daten = gzip.decompress(daten)
    return daten


def _ddg_pdf_links(frage: str) -> list[str]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(frage)
    html = _hole(url, 3 * 1024 * 1024).decode("utf-8", "replace")
    ziele = []
    # DDG verlinkt Ergebnisse als /l/?uddg=<urlencodiertes Ziel>
    for m in re.finditer(r'uddg=([^&"]+)', html):
        ziel = urllib.parse.unquote(m.group(1))
        if ziel.lower().split("?")[0].endswith(".pdf") and ziel not in ziele:
            ziele.append(ziel)
    # Direkte PDF-Links (falls DDG mal ohne Redirect ausliefert)
    for m in re.finditer(r'href="(https?://[^"]+\.pdf)"', html, re.I):
        if m.group(1) not in ziele:
            ziele.append(m.group(1))
    return ziele


def _bing_pdf_links(frage: str) -> list[str]:
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(frage)
    html = _hole(url, 3 * 1024 * 1024).decode("utf-8", "replace")
    ziele = []
    for m in re.finditer(r'href="(https?://[^"]+\.pdf)"', html, re.I):
        if "bing.com" not in m.group(1) and m.group(1) not in ziele:
            ziele.append(m.group(1))
    return ziele


def _suche_kandidaten(hersteller: str, name: str) -> list[str]:
    """PDF-Kandidaten aus mehreren Suchanfragen; DDG zuerst, Bing als Rückfallebene."""
    fragen = [
        f"{hersteller} {name} Betriebsanleitung filetype:pdf",
        f"{hersteller} {name} Bedienungsanleitung filetype:pdf",
        f"{hersteller} {name} operating manual filetype:pdf",
    ]
    ziele: list[str] = []
    fehler = 0
    for suchlauf in (_ddg_pdf_links, _bing_pdf_links):
        for frage in fragen:
            try:
                for z in suchlauf(frage):
                    if z not in ziele:
                        ziele.append(z)
            except Exception as exc:  # Netz-/Blockfehler -> nächste Anfrage probieren
                logger.warning("Suche fehlgeschlagen (%s, %s): %s",
                               suchlauf.__name__, frage, exc)
                fehler += 1
            if len(ziele) >= 10:
                break
        if ziele:  # Bing nur bemühen, wenn DDG nichts geliefert hat
            break
    if not ziele and fehler == 2 * len(fragen):
        raise AnleitungNichtGefunden("Websuche nicht erreichbar.")

    # Ranking: Hersteller-Domain > "Anleitung/Manual" im Pfad > Modell-Begriffe im Pfad.
    schluessel = re.sub(r"[^a-z0-9]", "", hersteller.lower())
    modell_begriffe = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 2]

    def _wertung(u: str) -> int:
        teile = urllib.parse.urlparse(u)
        pfad = urllib.parse.unquote(teile.path).lower()
        punkte = 0
        if schluessel and schluessel in teile.netloc.lower():
            punkte -= 4
        if re.search(r"anleitung|bedienung|manual|instruction|operating", pfad):
            punkte -= 3
        punkte -= sum(1 for t in modell_begriffe if t in pfad)
        return punkte

    ziele.sort(key=_wertung)
    return ziele[:MAX_KANDIDATEN]


def _verkleinere_pdf(daten: bytes) -> bytes:
    """Verkleinert ein PDF per Ghostscript (/ebook). Gibt Original zurück, wenn gs fehlt."""
    if shutil.which("gs") is None:
        return daten
    with tempfile.TemporaryDirectory() as tmp:
        quelle = Path(tmp) / "in.pdf"
        ziel = Path(tmp) / "out.pdf"
        quelle.write_bytes(daten)
        try:
            subprocess.run(
                ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
                 "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                 f"-sOutputFile={ziel}", str(quelle)],
                check=True, timeout=120,
            )
            klein = ziel.read_bytes()
            if klein[:5] == b"%PDF-" and len(klein) < len(daten):
                return klein
        except (subprocess.SubprocessError, OSError) as exc:
            logger.warning("Ghostscript-Verkleinerung fehlgeschlagen: %s", exc)
    return daten


def _waehle_mit_ki(kandidaten: list[str], hersteller: str, name: str) -> list[str]:
    """Lässt Claude die Kandidaten filtern/sortieren (offizielle Anleitung zuerst).

    Gibt bei KI-Problemen die heuristische Reihenfolge zurück. Sagt die KI
    ausdrücklich "keiner passt", wird AnleitungNichtGefunden geworfen - lieber
    keine Anleitung als eine Broschüre oder ein Etiketten-PDF.
    """
    if not kandidaten:
        return kandidaten
    try:
        from backend import ki_analyse
        if os.environ.get("WERKZEUG_KI_MOCK") or not ki_analyse.ist_konfiguriert():
            return kandidaten
        liste = "\n".join(f"{i}: {u}" for i, u in enumerate(kandidaten))
        antwort = ki_analyse.frage_text(
            "Websuche nach der offiziellen Bedienungs-/Betriebsanleitung für die "
            f"Maschine \"{hersteller} {name}\". Kandidaten-PDF-URLs:\n{liste}\n\n"
            "Antworte NUR mit einem JSON-Array der Indizes, sortiert nach "
            "Wahrscheinlichkeit, dass es die offizielle Bedienungs-/Betriebs"
            "anleitung genau dieses Geräts ist. Broschüren, Kataloge, Etiketten/"
            "Label, Ersatzteillisten und Anleitungen anderer Modelle weglassen. "
            "Leeres Array [], wenn nichts passt."
        )
        m = re.search(r"\[[^\]]*\]", antwort)
        indizes = json.loads(m.group(0)) if m else None
        if indizes is None:
            return kandidaten
        gewaehlt = [kandidaten[i] for i in indizes
                    if isinstance(i, int) and 0 <= i < len(kandidaten)]
        if not gewaehlt:
            raise AnleitungNichtGefunden(
                "Unter den Suchtreffern war keine offizielle Bedienungsanleitung."
            )
        return gewaehlt
    except AnleitungNichtGefunden:
        raise
    except Exception as exc:
        logger.warning("KI-Auswahl fehlgeschlagen, nutze Heuristik: %s", exc)
        return kandidaten


def suche_anleitung(hersteller: str, name: str) -> tuple[bytes, str]:
    """Sucht + lädt die Anleitung. Rückgabe: (pdf_bytes <= 10 MB, quelle_url)."""
    kandidaten = _waehle_mit_ki(_suche_kandidaten(hersteller, name), hersteller, name)
    for ziel in kandidaten:
        try:
            daten = _hole(ziel, MAX_DOWNLOAD_BYTES)
        except Exception as exc:
            logger.info("Kandidat nicht ladbar (%s): %s", ziel, exc)
            continue
        if daten[:5] != b"%PDF-":
            continue
        if len(daten) > MAX_PDF_BYTES:
            daten = _verkleinere_pdf(daten)
        if len(daten) <= MAX_PDF_BYTES:
            return daten, ziel
        logger.info("Kandidat trotz Verkleinerung zu groß (%s)", ziel)
    raise AnleitungNichtGefunden("Keine passende PDF-Anleitung gefunden.")
