"""KI-Analyse von Typenschild-Fotos via AWS Bedrock (Claude).

Liest aus 1-n Fotos Hersteller, Modell und Seriennummer und liefert
Vorschlagswerte für das Maschinen-Formular. Konfiguration über Env:
AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION / BEDROCK_MODEL_ID.
WERKZEUG_KI_MOCK=1 liefert eine feste Beispielantwort (lokale Entwicklung).
"""

import json
import logging
import os

logger = logging.getLogger("werkzeug_app.ki_analyse")

STANDARD_MODEL_ID = "eu.anthropic.claude-sonnet-4-6"
STANDARD_REGION = "eu-central-1"

# Maximallängen wie in Maschine/MaschineCreate.
_MAX_LAENGEN = {"name": 120, "hersteller": 80, "seriennummer": 80}
FELDER = ("name", "hersteller", "seriennummer", "beschreibung", "hinweis")

PROMPT = """Du siehst Fotos von Typenschildern/Etiketten einer Werkstatt-Maschine.
Lies die Angaben und antworte NUR mit einem JSON-Objekt in genau dieser Form:
{"name": ..., "hersteller": ..., "seriennummer": ..., "beschreibung": ..., "hinweis": ...}

- name: Hersteller + Modellbezeichnung (z. B. "Lamello TOP 21")
- hersteller: nur der Herstellername (z. B. "Lamello")
- seriennummer: die Seriennummer exakt wie abgebildet (Beschriftungen wie
  "Ser. Nr.", "No.", "S/N"). Interne Aufkleber wie "Maschine 2" sind KEINE
  Seriennummer.
- beschreibung: ein kurzer deutscher Satz zur Maschinenart, falls erkennbar
  (z. B. "Flachdübelfräse"), sonst null
- hinweis: null, oder ein kurzer deutscher Hinweis, wenn etwas unsicher ist
  oder die Fotos verschiedene Maschinen zeigen (dann die Angaben der am
  deutlichsten gezeigten Maschine nehmen und das hier vermerken)

Nicht sicher Lesbares als null zurückgeben - nicht raten."""

_MOCK_ANTWORT = {
    "name": "Lamello TOP 21",
    "hersteller": "Lamello",
    "seriennummer": "L44E-1617318",
    "beschreibung": "Flachdübelfräse",
    "hinweis": "Mock-Antwort (WERKZEUG_KI_MOCK=1) - kein echter KI-Aufruf.",
}


class KIAnalyseFehler(Exception):
    """Bedrock nicht konfiguriert/erreichbar oder Antwort unbrauchbar."""


def ist_konfiguriert() -> bool:
    return bool(
        os.environ.get("WERKZEUG_KI_MOCK")
        or (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))
    )


def analysiere_fotos(bilder: list[bytes]) -> dict:
    """Analysiert JPEG-Bilder, gibt dict mit den Feldern aus FELDER zurück."""
    if os.environ.get("WERKZEUG_KI_MOCK"):
        return dict(_MOCK_ANTWORT)
    if not ist_konfiguriert():
        raise KIAnalyseFehler("KI-Analyse ist nicht konfiguriert (AWS-Zugangsdaten fehlen).")
    return _parse_antwort(_rufe_bedrock(bilder))


def frage_text(prompt: str, max_tokens: int = 300) -> str:
    """Reine Text-Frage an Claude (Bedrock). Wirft KIAnalyseFehler bei Problemen."""
    if not ist_konfiguriert() or os.environ.get("WERKZEUG_KI_MOCK"):
        raise KIAnalyseFehler("KI-Analyse ist nicht konfiguriert.")
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", STANDARD_REGION),
    )
    try:
        antwort = client.converse(
            modelId=os.environ.get("BEDROCK_MODEL_ID", STANDARD_MODEL_ID),
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        return antwort["output"]["message"]["content"][0]["text"]
    except (BotoCoreError, ClientError, KeyError, IndexError, TypeError) as exc:
        raise KIAnalyseFehler("KI-Dienst ist gerade nicht erreichbar.") from exc


def _rufe_bedrock(bilder: list[bytes]) -> str:
    # Import erst hier: Tests/Mock-Betrieb brauchen boto3 nicht.
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", STANDARD_REGION),
    )
    content = [{"image": {"format": "jpeg", "source": {"bytes": b}}} for b in bilder]
    content.append({"text": PROMPT})
    try:
        antwort = client.converse(
            modelId=os.environ.get("BEDROCK_MODEL_ID", STANDARD_MODEL_ID),
            messages=[{"role": "user", "content": content}],
            inferenceConfig={"maxTokens": 500, "temperature": 0},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.warning("Bedrock-Aufruf fehlgeschlagen: %s", exc)
        raise KIAnalyseFehler("KI-Dienst ist gerade nicht erreichbar.") from exc

    try:
        return antwort["output"]["message"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise KIAnalyseFehler("Unerwartete Antwort vom KI-Dienst.") from exc


def _parse_antwort(text: str) -> dict:
    """Extrahiert das JSON-Objekt aus der Modellantwort und normalisiert es."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    # Zur Sicherheit auf das erste {...} eingrenzen (falls das Modell drumherum redet).
    start, ende = text.find("{"), text.rfind("}")
    if start == -1 or ende == -1:
        raise KIAnalyseFehler("KI-Antwort enthielt kein JSON.")
    try:
        roh = json.loads(text[start : ende + 1])
    except json.JSONDecodeError as exc:
        raise KIAnalyseFehler("KI-Antwort war kein gültiges JSON.") from exc
    if not isinstance(roh, dict):
        raise KIAnalyseFehler("KI-Antwort hatte ein unerwartetes Format.")

    ergebnis = {}
    for feld in FELDER:
        wert = roh.get(feld)
        if isinstance(wert, str):
            wert = wert.strip() or None
        elif wert is not None:
            wert = str(wert)
        if wert and feld in _MAX_LAENGEN:
            wert = wert[: _MAX_LAENGEN[feld]]
        ergebnis[feld] = wert
    return ergebnis
