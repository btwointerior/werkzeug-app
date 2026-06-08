# QR-Code-Scanner auf der Startseite — Design

**Status:** Freigegeben (2026-06-06)

## Ziel

Mitarbeiter sollen eine Maschine per **Kamera-QR-Scan** öffnen, statt den Code zu
tippen. Auf der Startseite („Meine Ausleihen") kommt ein prominenter
**„QR-Code scannen"**-Button; zusätzlich öffnet der vorhandene **„Code"**-Button
in der unteren Navigation denselben Scanner. Langfristige Vision: Mitarbeiter
scannen nur noch den QR und landen direkt auf der Maschine.

## Ausgangslage (aus dem Code)

- Die gedruckten QR-Etiketten kodieren bereits die volle URL
  `{BASE_URL}/#/m/{maschinen_code}` (`backend/qr.py`). Native Handy-Kameras
  öffnen damit schon jetzt direkt die Maschinenseite — es fehlt nur der
  **In-App-Scanner**.
- Route `#/m/(.+)` rendert die Maschine per Code; Endpunkt
  `GET /api/maschinen/by-code/{code}` existiert. **Kein Backend-Bedarf.**
- Startseite `views/meine.js` hat aktuell nur eine manuelle Code-Eingabe.
- Untere Nav (`app.js`, Funktion `askCode`) öffnet einen Tipp-Dialog.

## Entscheidungen (aus dem Brainstorming)

| Frage | Entscheidung |
|-------|--------------|
| Geräte | Gemischt iPhone (Safari) + Android (Chrome) → plattformübergreifend |
| Bibliothek | `jsQR` (MIT, ~50 KB), **lokal vendored** (kein Laufzeit-CDN) |
| Ansatz | Eigenes dunkles Overlay + `getUserMedia` + `jsQR` (Ansatz A) |
| Platzierung | Beides: großer Button auf Startseite **und** unterer „Code"-Button |
| Fallback | Bei Kamera-Problem/Abbruch → bestehende manuelle Eingabe |

## Architektur

Eine **wiederverwendbare Scanner-Komponente** `frontend/js/scanner.js`, genutzt
von Startseite und unterer Navigation. Kein Build-Step, Vanilla-JS-ES-Module,
konsistent mit dem bestehenden Frontend. `jsQR` wird als lokale Datei unter
`frontend/js/vendor/jsqr.min.js` abgelegt (offlinefähig, wird vom Deploy via
rsync mit-synchronisiert; kein externer Laufzeit-Abhang).

### `frontend/js/scanner.js`

Zwei Exports:

**`parseScan(text) -> string | null`** — reine Funktion, der testbare Kern.
- Enthält der Text `#/m/<code>` (unsere QR-URL): `<code>` extrahieren,
  `decodeURIComponent`, trimmen, `toUpperCase()`.
- Sonst, wenn der getrimmte Text wie ein Code aussieht (nicht leer, keine
  Leerzeichen, kein `://`): den getrimmten Text `toUpperCase()` als Code.
- Sonst `null`.

**`scanQr() -> Promise<string | null>`**
- Baut ein Vollbild-Overlay (siehe UX) in `#modal-root` analog zu `ui.modal`.
- `navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })`,
  Stream an ein `<video autoplay playsinline muted>`.
- Decode-Schleife via `requestAnimationFrame`: aktuelles Frame in ein
  (off-screen) `<canvas>` zeichnen, `ctx.getImageData` an `jsQR` geben.
  - Treffer → `parseScan(result.data)`:
    - gültiger Code → Rahmen kurz grün, Kamera stoppen, Overlay schließen,
      Promise mit dem Code auflösen.
    - `null` → Hinweis „Kein gültiger Maschinen-Code", Schleife läuft weiter.
- „Abbrechen" → Kamera stoppen, schließen, mit `null` auflösen.
- Kamera-Fehler (`NotAllowedError`/`NotFoundError`/kein `mediaDevices`) →
  Fehlerzustand im Overlay mit Button „Code manuell eingeben"; Auswahl löst mit
  `null` auf (Aufrufer öffnet Fallback).
- **Aufräumen:** in allen Endpfaden alle `stream.getTracks().forEach(t => t.stop())`
  und `requestAnimationFrame` abbrechen.

### Integration

**`views/meine.js`** — über der manuellen Eingabe ein primärer Button
„📷 QR-Code scannen" (`btnClasses('primary')`, volle Breite):
```js
const code = await scanQr();
if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
else document.getElementById('code-input')?.focus();
```
Die manuelle Eingabe bleibt darunter als Fallback.

**`app.js`** — die untere „Code"-Aktion ruft zuerst den Scanner, sonst den
bisherigen Tipp-Dialog:
```js
const code = await scanQr();
if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
else await askCode();   // bestehende manuelle Eingabe als Fallback
```
`askCode` bleibt unverändert erhalten.

## UX / Overlay

- Vollbild, fast schwarzer Hintergrund (`bg-bg`/`bg-black`), Live-Kamerabild
  formatfüllend (`object-cover`).
- Mittiger quadratischer **Ziel-Rahmen** mit Lime-Rand (`border-accent`) als
  Visierhilfe; darunter Hinweis „QR-Code der Maschine in den Rahmen halten".
- Oben Titel „QR-Code scannen"; unten großer **„Abbrechen"**-Button (≥48 px).
- Treffer: Rahmen kurz `border-ok` (grün), dann Navigation.
- Fehlerzustand: kurze Meldung + Button „Code manuell eingeben".

## Tests / Verifikation

- **`parseScan`** über klar definierte Fälle prüfen (reine Logik, der testbare
  Kern): volle QR-URL → Code; roher Code (klein/groß) → Großbuchstaben-Code;
  leerer/whitespace/`http…`-Müll ohne `#/m/` → `null`. Da das Frontend keine
  JS-Test-Harness hat, manuell verifiziert; Logik bewusst klein/offensichtlich.
- **Backend:** keine Änderung → bestehende pytest-Suite (32 Tests) bleibt grün.
- **Manuell:** iPhone/Safari **und** Android/Chrome über HTTPS: Startseite →
  „QR-Code scannen" → echten QR scannen → richtige Maschine; ebenso der untere
  „Code"-Button. Fallback bei abgelehnter Kamera-Erlaubnis und auf Desktop ohne
  Kamera. Nach Schließen läuft die Kamera nicht weiter.

## Bewusst nicht im Scope (YAGNI)

- Kein Taschenlampen-/Blitz-Schalter, keine Front/Rück-Umschaltung.
- Kein Scannen aus einem Galeriebild, kein Mehrfach-/Dauerscan.
- Keine Backend-/Datenmodell-/Routen-Änderung.
- Keine Änderung an den gedruckten QR-Etiketten (kodieren bereits die URL).
