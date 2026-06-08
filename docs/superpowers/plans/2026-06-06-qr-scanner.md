# QR-Code-Scanner auf der Startseite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mitarbeiter öffnen eine Maschine per Kamera-QR-Scan — über einen großen Button auf der Startseite und über den „Code"-Button der unteren Navigation.

**Architecture:** Wiederverwendbare Vanilla-JS-Komponente `frontend/js/scanner.js` mit der reinen Funktion `parseScan` (TDD via Node-Test-Runner) und `scanQr` (dunkles Vollbild-Overlay, `getUserMedia` + lokal eingebundenes `jsQR`). Eingebunden in `meine.js` und `app.js`, mit manueller Code-Eingabe als Fallback. Kein Backend-, Routen- oder QR-Etiketten-Bedarf.

**Tech Stack:** Vanilla-JS-ES-Module, Tailwind via CDN, `jsQR` (MIT, lokal vendored), Node `node:test` für die Logik, pytest als Regressionsnetz.

**Spec:** `docs/superpowers/specs/2026-06-06-qr-scanner-design.md`

---

## Verifikations-Grundsätze (für ALLE Tasks)

- **Logik:** `parseScan` wird mit `node --test` geprüft (echtes TDD).
- **Regression Backend:** `~/.venvs/werkzeug/bin/python -m pytest -q` bleibt `32 passed` (keine Backend-Änderung).
- **Kamera-UI:** nur manuell prüfbar (Browser/Handy). Wo „manuell" steht, ist das beabsichtigt.

**Node:** `node` (v22, `node:test` vorhanden). **Lokal starten** für manuelle Checks:
```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m uvicorn backend.main:app --reload --port 8000
```
Kamera braucht HTTPS oder `http://localhost` — `localhost:8000` genügt zum Testen.

---

## Datei-Übersicht

| Datei | Verantwortung | Aktion |
|-------|---------------|--------|
| `frontend/package.json` | `{"type":"module"}` — lässt Node die Frontend-`.js` als ESM importieren (nur für Tests; Browser ignoriert es) | Create |
| `frontend/js/scanner.js` | `parseScan` (rein) + `scanQr` (Overlay/Kamera) | Create |
| `frontend/js/vendor/jsqr.min.js` | lokal eingebundene jsQR-Bibliothek | Create (Download) |
| `tests/js/parse_scan.test.mjs` | Node-Tests für `parseScan` | Create |
| `frontend/index.html` | `<script>` für jsQR vor dem App-Modul | Modify |
| `frontend/js/views/meine.js` | großer „QR-Code scannen"-Button | Modify |
| `frontend/js/app.js` | unterer „Code"-Button → Scanner (Fallback `askCode`) | Modify |

---

## Task 0: Baseline

- [ ] **Step 1: Branch + Tooling prüfen**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
git rev-parse --abbrev-ref HEAD          # erwartet: feature/qr-scanner
node --version                            # erwartet: v18+ (vorhanden: v22)
~/.venvs/werkzeug/bin/python -m pytest -q # erwartet: 32 passed
```

---

## Task 1: `parseScan` (reine Logik, TDD)

**Files:**
- Create: `frontend/package.json`
- Create: `tests/js/parse_scan.test.mjs`
- Create: `frontend/js/scanner.js`

- [ ] **Step 1: ESM für Node aktivieren**

Create `frontend/package.json`:
```json
{
  "type": "module",
  "private": true
}
```
(Der Browser lädt JS über `<script type="module">` und ignoriert diese Datei; sie sorgt nur dafür, dass Node die `frontend/js/*.js` als ES-Module importieren kann.)

- [ ] **Step 2: Failing test schreiben**

Create `tests/js/parse_scan.test.mjs`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseScan } from '../../frontend/js/scanner.js';

test('volle QR-URL → Code', () => {
  assert.equal(parseScan('https://werkzeug.b2interior.de/#/m/M-0042'), 'M-0042');
});

test('QR-URL mit Kleinbuchstaben → Großbuchstaben', () => {
  assert.equal(parseScan('https://werkzeug.b2interior.de/#/m/m-0042'), 'M-0042');
});

test('nur Hash-Route → Code', () => {
  assert.equal(parseScan('#/m/M-0099'), 'M-0099');
});

test('roher Code → unverändert (groß)', () => {
  assert.equal(parseScan('M-0042'), 'M-0042');
  assert.equal(parseScan('m-0042'), 'M-0042');
});

test('Whitespace wird getrimmt', () => {
  assert.equal(parseScan('  M-0042  '), 'M-0042');
});

test('leer / nur Whitespace → null', () => {
  assert.equal(parseScan(''), null);
  assert.equal(parseScan('   '), null);
});

test('fremde URL ohne #/m/ → null', () => {
  assert.equal(parseScan('https://example.com/etwas'), null);
});

test('Nicht-String → null', () => {
  assert.equal(parseScan(null), null);
  assert.equal(parseScan(undefined), null);
});
```

- [ ] **Step 3: Test ausführen, Fehlschlag bestätigen**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
node --test tests/js/parse_scan.test.mjs
```
Erwartet: FAIL (Modul `frontend/js/scanner.js` existiert nicht / `parseScan` undefiniert).

- [ ] **Step 4: `scanner.js` mit `parseScan` anlegen (minimal)**

Create `frontend/js/scanner.js`:
```js
// Wiederverwendbarer QR-Scanner. parseScan ist rein und unit-getestet;
// scanQr (in einem späteren Schritt) kapselt Kamera + Overlay.

const MARKER = '#/m/';

// Macht aus einem gescannten String den Maschinen-Code (oder null).
// Akzeptiert die QR-URL (…/#/m/CODE) ebenso wie einen rohen Code.
export function parseScan(text) {
  if (typeof text !== 'string') return null;
  const s = text.trim();
  if (!s) return null;

  const i = s.indexOf(MARKER);
  if (i !== -1) {
    const raw = s.slice(i + MARKER.length).trim();
    if (!raw) return null;
    try {
      return decodeURIComponent(raw).trim().toUpperCase();
    } catch {
      return raw.toUpperCase();
    }
  }

  // Kein Marker: nur einen "nackten" Code akzeptieren (kein Schema, kein Whitespace).
  if (s.includes('://') || /\s/.test(s)) return null;
  return s.toUpperCase();
}
```

- [ ] **Step 5: Test ausführen, Erfolg bestätigen**

```bash
node --test tests/js/parse_scan.test.mjs
```
Erwartet: alle Tests `pass` (8 Tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/js/scanner.js tests/js/parse_scan.test.mjs
git commit -m "QR-Scanner: parseScan (reine Logik) mit Node-Tests"
```
(Leerzeile + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`)

---

## Task 2: jsQR lokal einbinden

**Files:**
- Create: `frontend/js/vendor/jsqr.min.js`
- Modify: `frontend/index.html`

- [ ] **Step 1: jsQR herunterladen (gepinnte Version)**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
mkdir -p frontend/js/vendor
curl -fsSL https://unpkg.com/jsqr@1.4.0/dist/jsQR.js -o frontend/js/vendor/jsqr.min.js
```

- [ ] **Step 2: Download verifizieren**

```bash
ls -l frontend/js/vendor/jsqr.min.js          # > 50 KB
grep -c "jsQR" frontend/js/vendor/jsqr.min.js # > 0 (Bibliothek definiert global jsQR)
```
Erwartet: Datei existiert, Größe > 50 KB, Treffer für `jsQR`. Falls der Download fehlschlägt (HTTP-Fehler), STOPP und melden — nicht raten.

- [ ] **Step 3: jsQR im `index.html` einbinden (vor dem App-Modul)**

In `frontend/index.html` die Zeile
```html
  <script type="module" src="/static/js/app.js"></script>
```
ersetzen durch:
```html
  <script src="/static/js/vendor/jsqr.min.js"></script>
  <script type="module" src="/static/js/app.js"></script>
```
(Der klassische `<script>` läuft vor dem deferred Modul → `window.jsQR` ist verfügbar, wenn `scanQr` aufgerufen wird.)

- [ ] **Step 4: Verifikation**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q   # 32 passed
node --test tests/js/parse_scan.test.mjs    # weiterhin grün
```
Manuell (optional jetzt, spätestens in Task 6): App starten, im Browser-Konsolen-Check `typeof jsQR` → `"function"`.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/vendor/jsqr.min.js frontend/index.html
git commit -m "QR-Scanner: jsQR (v1.4.0) lokal einbinden"
```
(Leerzeile + Co-Authored-By-Zeile wie oben.)

---

## Task 3: `scanQr()` — Kamera-Overlay

**Files:**
- Modify: `frontend/js/scanner.js`

- [ ] **Step 1: Import + `scanQr` ergänzen**

Am Anfang von `frontend/js/scanner.js`, VOR `const MARKER`, einfügen:
```js
import { btnClasses } from './ui.js';
```

Ans ENDE von `frontend/js/scanner.js` anfügen:
```js
// Öffnet ein Vollbild-Overlay mit Live-Kamera und scannt QR-Codes.
// Auflösung: gefundener Maschinen-Code (string) | null (Abbruch/Kamera nicht möglich).
export function scanQr() {
  return new Promise((resolve) => {
    const root = document.getElementById('modal-root');
    let stream = null;
    let raf = 0;
    let done = false;

    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 z-50 bg-black flex flex-col';
    overlay.innerHTML = `
      <div class="px-4 py-3 text-txt font-semibold">QR-Code scannen</div>
      <div class="relative flex-1 overflow-hidden">
        <video class="absolute inset-0 w-full h-full object-cover" playsinline muted></video>
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div id="qr-frame" class="w-64 h-64 max-w-[70vw] max-h-[70vw] rounded-2xl border-4 border-accent"></div>
        </div>
        <div id="qr-hint" class="absolute bottom-4 left-0 right-0 text-center text-txt-2 text-sm px-4">
          QR-Code der Maschine in den Rahmen halten
        </div>
      </div>
      <div class="p-4">
        <button id="qr-cancel" class="${btnClasses('secondary')} w-full">Abbrechen</button>
      </div>`;
    root.appendChild(overlay);

    const video = overlay.querySelector('video');
    const frame = overlay.querySelector('#qr-frame');
    const hint = overlay.querySelector('#qr-hint');
    const cancelBtn = overlay.querySelector('#qr-cancel');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    const cleanup = () => {
      if (raf) cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach((t) => t.stop());
      overlay.remove();
    };
    const finish = (value) => {
      if (done) return;
      done = true;
      cleanup();
      resolve(value);
    };

    cancelBtn.onclick = () => finish(null);

    const showError = () => {
      hint.textContent = 'Kamerazugriff nicht möglich.';
      cancelBtn.textContent = 'Code manuell eingeben';
    };

    const tick = () => {
      if (done) return;
      if (video.readyState === video.HAVE_ENOUGH_DATA && video.videoWidth) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const result = window.jsQR ? window.jsQR(img.data, img.width, img.height) : null;
        if (result) {
          const code = parseScan(result.data);
          if (code) {
            frame.classList.remove('border-accent');
            frame.classList.add('border-ok');
            finish(code);
            return;
          }
          hint.textContent = 'Kein gültiger Maschinen-Code.';
        }
      }
      raf = requestAnimationFrame(tick);
    };

    const md = navigator.mediaDevices;
    if (!md || !md.getUserMedia) {
      showError();
      return;
    }
    md.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        stream = s;
        video.srcObject = s;
        return video.play();
      })
      .then(() => { raf = requestAnimationFrame(tick); })
      .catch(() => showError());
  });
}
```

- [ ] **Step 2: Verifikation (Logik unberührt)**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
node --test tests/js/parse_scan.test.mjs   # weiterhin alle grün
~/.venvs/werkzeug/bin/python -m pytest -q   # 32 passed
```
(Hinweis: Der Node-Import von `scanner.js` zieht jetzt `./ui.js` mit; das ist zulässig, da `ui.js` auf Top-Level nur Funktions-/Konstanten-Definitionen hat und `scanQr` erst beim Aufruf DOM/Kamera nutzt. Falls der Test dadurch fehlschlägt, melden — nicht raten.)

- [ ] **Step 3: Commit**

```bash
git add frontend/js/scanner.js
git commit -m "QR-Scanner: scanQr() Kamera-Overlay (jsQR)"
```
(Leerzeile + Co-Authored-By-Zeile.)

---

## Task 4: Startseiten-Button (`meine.js`)

**Files:**
- Modify: `frontend/js/views/meine.js`

- [ ] **Step 1: `scanQr` importieren**

In `frontend/js/views/meine.js` die Import-Zeile von `../api.js` unverändert lassen und nach den bestehenden Imports ergänzen:
```js
import { scanQr } from '../scanner.js';
```

- [ ] **Step 2: Scan-Button ins Markup einfügen**

In `renderMeine`, im `app.innerHTML`-Template, direkt NACH
```html
      <h1 class="text-2xl font-bold text-txt mb-4">Meine Ausleihen</h1>
```
einfügen:
```html
      <button id="scan-btn" class="${btnClasses('primary')} w-full mb-4 text-base">📷 QR-Code scannen</button>
```
(`btnClasses` ist in `meine.js` bereits importiert.)

- [ ] **Step 3: Button verdrahten**

In `renderMeine`, direkt NACH dem bestehenden Block
```js
  document.getElementById('code-form').onsubmit = (e) => {
    e.preventDefault();
    const code = document.getElementById('code-input').value.trim().toUpperCase();
    if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  };
```
einfügen:
```js
  document.getElementById('scan-btn').onclick = async () => {
    const code = await scanQr();
    if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
    else document.getElementById('code-input')?.focus();
  };
```

- [ ] **Step 4: Verifikation**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q   # 32 passed
node --test tests/js/parse_scan.test.mjs    # grün
```
Manuell: Startseite zeigt oben den Lime-Button „📷 QR-Code scannen".

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/meine.js
git commit -m "QR-Scanner: Scan-Button auf der Startseite"
```
(Leerzeile + Co-Authored-By-Zeile.)

---

## Task 5: Untere Navigation (`app.js`)

**Files:**
- Modify: `frontend/js/app.js`

- [ ] **Step 1: `scanQr` importieren**

In `frontend/js/app.js` die bestehende ui-Import-Zeile
```js
import { btnClasses, escapeHtml, logoMarkup, modal, toast } from './ui.js';
```
unverändert lassen und darunter ergänzen:
```js
import { scanQr } from './scanner.js';
```

- [ ] **Step 2: Hilfsfunktion `scanOrAsk` ergänzen**

Direkt VOR der bestehenden Funktion `async function askCode()` einfügen:
```js
async function scanOrAsk() {
  const code = await scanQr();
  if (code) location.hash = `#/m/${encodeURIComponent(code)}`;
  else await askCode();   // Abbruch/Kamera nicht möglich → manuelle Eingabe
}
```

- [ ] **Step 3: Nav-Aktion umstellen**

In `renderChrome`, im `links`-Array, die Zeile
```js
    { label: 'Code',   icon: '🔍', action: askCode },
```
ersetzen durch:
```js
    { label: 'Code',   icon: '🔍', action: scanOrAsk },
```
(`askCode` bleibt als Funktion erhalten und wird von `scanOrAsk` als Fallback genutzt.)

- [ ] **Step 4: Verifikation**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q   # 32 passed
node --test tests/js/parse_scan.test.mjs    # grün
grep -nE "bg-white|(bg|text|border)-slate-[0-9]+" frontend/js/scanner.js frontend/js/views/meine.js frontend/js/app.js
```
Letzter Grep erwartet: keine Ausgabe (Overlay/Buttons nutzen Tokens). Manuell: unterer „Code"-Button öffnet den Scanner.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/app.js
git commit -m "QR-Scanner: unterer Code-Button öffnet Scanner (Fallback askCode)"
```
(Leerzeile + Co-Authored-By-Zeile.)

---

## Task 6: Gesamt-Verifikation & Abschluss

**Files:** keine Änderung.

- [ ] **Step 1: Alle automatisierten Tests grün**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q   # 32 passed
node --test tests/js/parse_scan.test.mjs    # 8 Tests grün
```

- [ ] **Step 2: Manueller Durchlauf (Kamera)**

App starten (`uvicorn … --port 8000`) und im Browser auf `http://localhost:8000`:
- Startseite → „📷 QR-Code scannen" → Kamerafreigabe erlauben → einen QR (z. B. ein generiertes Maschinen-Etikett am Bildschirm) in den Rahmen halten → landet auf der richtigen Maschine.
- Unterer „Code"-Button → öffnet denselben Scanner.
- **Fallback:** Kamera ablehnen → Button wird „Code manuell eingeben"; auf der Startseite springt der Fokus ins Eingabefeld, unten öffnet sich der Tipp-Dialog.
- **Sauberkeit:** nach Schließen/Treffer läuft die Kamera nicht weiter (kein Kamera-Indikator mehr).
- Wenn möglich zusätzlich je einmal auf **iPhone/Safari** und **Android/Chrome** über die HTTPS-URL.

- [ ] **Step 3: Branch abschließen**

Mit dem `superpowers:finishing-a-development-branch`-Skill (Merge nach `main` / Push / Deploy nach Wunsch).

---

## Self-Review-Notiz (Plan ↔ Spec)

- Spec „parseScan (URL/roher Code/Normalisierung/null)" → Task 1 (mit Tests). ✓
- Spec „jsQR lokal vendored" → Task 2. ✓
- Spec „scanQr Overlay + getUserMedia(environment) + Decode-Loop + Cleanup + Fehlerzustand" → Task 3. ✓
- Spec „Integration meine.js (Scan-Button, Fallback Eingabe)" → Task 4. ✓
- Spec „Integration app.js (Code-Button → Scanner, Fallback askCode)" → Task 5. ✓
- Spec „UX: dunkles Overlay, Lime-Rahmen, Hinweis, Abbrechen, Treffer grün, Fehler→manuell" → Task 3 (Markup/Logik). ✓
- Spec „kein Backend/Routen/QR-Etiketten-Bedarf" → eingehalten (keine solchen Tasks). ✓
- Spec „Tests: parseScan-Fälle + pytest grün + manuell" → Tasks 1/6. ✓
- Spec „YAGNI (kein Blitz/Kameraumschaltung/Galerie/Mehrfachscan)" → nicht enthalten. ✓
