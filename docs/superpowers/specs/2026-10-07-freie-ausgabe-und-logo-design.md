# Freie Ausgabe (Geräte ohne Code) + Firmenlogo — Design

Datum: 2026-10-07 · Status: vom Betreiber freigegeben („ja passt, leg los")

## 1. Ziel

Kleinteile ohne eigenen Maschinen-Code (Schraubzwingen, Spritzen, …) sollen
trotzdem nachvollziehbar ausgegeben werden können. Beleg ist ein **Pflicht-Foto**,
dazu eine Textbeschreibung („2 Schraubzwingen 300 mm") und der Empfänger.
Rückgabe schließt den Eintrag ab; der Admin sieht alles in einer Historie.

Zusätzlich soll das Firmenlogo **bühler² interior** in der App sichtbar sein.

## 2. Nicht-Ziele (bewusst weggelassen)

- Keine Stammdaten/Bestandsführung für Kleinteile (kein Mengenartikel).
- Kein Rückgabe-Foto, keine Stückzahl als eigenes Feld (steht im Text).
- Kein Löschen von Einträgen — nur Abschließen (sonst keine Historie).
- Keine Erinnerungs-Mails (gibt es für Maschinen heute auch nicht).

## 3. Datenmodell (neu, nur neue Tabellen → `create_all` legt sie beim Deploy an)

```
freie_ausgaben
  id, benutzer_id (FK benutzer, CASCADE), externes_team_id (FK externe_teams, NULL),
  beschreibung TEXT NOT NULL, ausgabe_zeitpunkt, rueckgabe_zeitpunkt NULL (idx),
  rueckgabe_kommentar NULL
freie_ausgabe_fotos
  id, ausgabe_id (FK freie_ausgaben, CASCADE), datei_pfad
```

Dateiname: `ausgabe_{ausgabe_id}_foto_{foto_id}.jpg` (im bestehenden `uploads/`,
Auslieferung über den bestehenden Datei-Token-Endpunkt `/uploads/{name}?t=`).
Benutzer-Löschung: Benutzer mit **offener** freier Ausgabe kann nicht gelöscht
werden (wie bei Maschinen); abgeschlossene Einträge werden mitgelöscht.

## 4. API

Neuer Router `backend/routers/freie_ausgabe_router.py`, Präfix `/api/freie-ausgaben`:

| Methode | Pfad | Wer | Zweck |
|---|---|---|---|
| POST | `` (multipart: `beschreibung`, `externes_team?`, `dateien` 1–3) | alle | anlegen; ohne Foto → 400 „Mindestens ein Foto ist Pflicht." |
| GET | `/meine` | alle | eigene offene Einträge |
| POST | `/{id}/zurueckgeben` (JSON `{kommentar?}`) | Eigentümer oder Admin | abschließen; schon zurück → 400 |
| GET | `/api/admin/freie-ausgaben?offen=true|false|alle&suche=` | Admin | Historie (neueste zuerst) |

Bild-Validierung (`_pruefe_bild_oder_400`) und Verkleinern (1600 px, JPEG 85)
wandern aus `admin_router.py` in ein gemeinsames Modul `backend/bilder.py`.

Response `FreieAusgabeOut`: id, beschreibung, benutzer (BenutzerKurz),
externes_team_name, ausgabe_zeitpunkt, rueckgabe_zeitpunkt, rueckgabe_kommentar,
dauer_tage, ist_offen, fotos [{id, url}] — URLs mit Datei-Token, analog `maschine_zu_out`.

`StatistikenOut` bekommt `ueberfaellige_freie` (offen > 7 Tage, gleiche Frist wie
Maschinen) und `offene_freie_anzahl`.

## 5. Frontend

**Einstieg** „📦 Ohne Code ausgeben": Knopf auf „Meine" (unter dem Scan-Knopf)
und auf „Geräte" (neben der Suche). Im globalen Scan-Overlay (Bottom-Nav
„Ausleihen") als dritte Option.

**Ablauf** (`frontend/js/views/freie_ausgabe.js`, Funktion `neueFreieAusgabe()`):
1. In-App-Kamera öffnet sofort (gemeinsames Modul `frontend/js/kamera.js`,
   aus `admin_maschine_form.js` herausgelöst; verkleinert Aufnahmen clientseitig
   auf max. 1600 px lange Kante, JPEG 0.85). Max. 3 Fotos.
2. Dialog „Ausgabe erfassen": Foto-Vorschauen (✕ entfernen, „📷 weiteres Foto",
   Datei-Auswahl als Fallback ohne Kamera), Pflicht-Text „Was wird ausgegeben?",
   Empfänger „Für mich" / „Externes Montageteam" (Datalist aus
   `/api/maschinen/externe-teams`, gleiche Logik wie beim Maschinen-Ausleihen).
   „Ausgeben" ist gesperrt, bis ≥1 Foto und Text vorhanden sind.
3. POST → Toast → „Meine" neu laden.

**Meine**: Abschnitt „Ohne Code ausgegeben" unter den Maschinen: Karte mit
Thumbnail, Text, Empfänger, „seit X Tagen", Knopf „Zurückgeben" → Dialog mit
optionaler Bemerkung → POST.

**Admin**: Dashboard-Kachel „📦 Freie Ausgaben" (mit Zähler offen) + Überfällig-
Liste zeigt freie Einträge mit. Neue Seite `#/admin/freie-ausgaben`: Reiter
Offen / Alle, Textsuche, Karten mit Fotos (Antippen → Vollbild in neuem Tab),
wer/an wen/von–bis/Bemerkung, „Abschließen" bei offenen Einträgen.

**Logo**: `frontend/assets/logo-buehler2-interior.svg` (Offwhite-Zweizeiler) auf
der Anmeldeseite über dem Titel; `frontend/assets/logo-b2.svg` (Offwhite-Zeichen
„b²") ersetzt das Naben-Icon in der Kopfzeile. App-Icon bleibt. Pfade laufen über
`logoMarkup()` in `ui.js` bzw. `/static/assets/…`, damit `sync-assets.mjs` sie für
die iOS-App relativiert.

## 6. Tests

- pytest `tests/test_freie_ausgabe.py`: anlegen (mit/ohne Foto, Team-Find-or-Create,
  >3 Fotos), meine, zurückgeben (Eigentümer/Admin/Fremder 403/doppelt 400),
  Admin-Liste + Filter + Suche, Statistiken (überfällig/Zähler), Benutzer-Löschen
  mit offener Ausgabe blockiert.
- JS-Test für die Bildverkleinerung (Zielmaße) in `tests/js/kamera.test.mjs`.
- Puppeteer-E2E mit Fake-Kamera: Ausgabe → Meine → Rückgabe → Admin-Historie.

## 7. Deploy

`./deploy.sh --go` (neue Tabellen via `create_all` beim Restart, kein ALTER),
`git push`, TestFlight-Tag `app-v1.3.0` per Codemagic-API.
