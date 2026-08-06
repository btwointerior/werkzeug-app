# Design: Foto-basiertes Anlegen neuer Maschinen (KI-Analyse)

Datum: 2026-08-06 · Status: vom User freigegeben (Chat)

## Ziel

Beim Anlegen einer neuen Maschine macht der Admin Fotos der Typenschilder/Etiketten.
Eine KI (Claude via AWS Bedrock) liest daraus Hersteller, Modell und Seriennummer und
befüllt das Formular vor. Gerätenummer (Maschinen-Code) und Standort (Platznummer)
werden weiterhin manuell eingetragen. Welches Foto als Maschinen-Foto übernommen
wird, wählt der Admin manuell aus (oder keins).

## Backend

- **Neues Modul `backend/ki_analyse.py`**
  - `analysiere_fotos(bilder: list[bytes]) -> dict` — schickt die (bereits
    verkleinerten) JPEGs per `boto3` (bedrock-runtime, Converse-API) an
    `BEDROCK_MODEL_ID` (Standard `eu.anthropic.claude-sonnet-4-6`,
    Region `AWS_REGION`, Standard `eu-central-1`).
  - Strukturierter Prompt: Typenschilder/Etiketten lesen → JSON mit
    `name` (Hersteller + Modell, z. B. "Lamello TOP 21"), `hersteller`,
    `seriennummer`, `beschreibung` (kurz, optional), `hinweis` (optional —
    z. B. "Fotos zeigen zwei verschiedene Maschinen" oder "Seriennummer unsicher").
  - Nicht Erkennbares bleibt `null` — kein Raten.
  - Fehlerklasse `KIAnalyseFehler` bei fehlender Konfiguration/Bedrock-Fehlern.
  - Mock-Modus `WERKZEUG_KI_MOCK=1` für lokale Entwicklung (feste Beispielantwort);
    Tests patchen den Bedrock-Aufruf.
- **Neuer Endpunkt `POST /api/admin/maschinen/foto-analyse`** (nur Admin)
  - Multipart, 1–5 Bilder (JPG/PNG/WebP, je max. 10 MB — gleiche Regeln wie
    Foto-Upload inkl. Magic-Byte-Prüfung via Pillow).
  - Verkleinert jedes Bild auf max. 1568 px, JPEG q85, und ruft `analysiere_fotos`.
  - Antwort-Schema `FotoAnalyseOut`: `name`, `hersteller`, `seriennummer`,
    `beschreibung`, `hinweis` (alle optional/nullable).
  - 503 mit klarer Meldung, wenn KI nicht konfiguriert/erreichbar — das Formular
    bleibt voll manuell nutzbar.
- **Dependency:** `boto3` in requirements (auf dem Server ins venv installieren);
  Env-Variablen (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`,
  `BEDROCK_MODEL_ID`) aus `/etc/konkordanz.env` in die systemd-Unit einbinden.
- Keine DB-Migration (keine neuen Spalten).

## Frontend (`admin_maschine_form.js`, nur Neu-Modus)

- Neue Sektion "Fotos analysieren" über dem Formular: Datei-Input
  (`accept="image/jpeg,image/png,image/webp"`, `multiple`, `capture=environment`)
  → iOS liefert damit automatisch JPEG statt HEIC.
- Thumbnails der gewählten Fotos; Antippen wählt genau eines als späteres
  Maschinen-Foto (erneut antippen = Abwahl; Standard: keins gewählt).
- Button "Analysieren": Spinner → Endpunkt → Felder Name/Hersteller/Seriennummer/
  Beschreibung werden vorbefüllt (KI-Vorschlag-Kennzeichnung, editierbar);
  `hinweis` wird als Warn-Text angezeigt. Bereits vom Admin ausgefüllte Felder
  werden nicht überschrieben.
- Beim "Anlegen": erst `POST /api/admin/maschinen`; danach, falls ein Foto gewählt
  ist, Upload über den bestehenden Endpunkt `POST /api/admin/maschinen/{id}/foto`.
  Schlägt nur der Foto-Upload fehl, bleibt die Maschine angelegt + Toast-Hinweis.

## Tests

- `tests/test_foto_analyse.py`: Erfolg (gemockter Bedrock), leere Erkennung,
  ungültige Datei → 400, zu viele Dateien → 400, kein Admin → 403,
  KI nicht konfiguriert → 503, Mock-Modus.
- Nach Deploy: echter End-to-End-Test mit den drei Beispiel-Fotos gegen Live.

## Fehlerfälle

- Nichts lesbar → Felder bleiben leer, Hinweis "nichts erkannt".
- Bedrock down/nicht konfiguriert → 503, Formular manuell nutzbar.
- Fotos zeigen mehrere Maschinen → KI nimmt die dominante und setzt `hinweis`.
