# iOS-App (Capacitor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Werkzeug-Webapp als native iOS-App (Capacitor, online-only) via TestFlight verfügbar machen; Webapp bleibt unverändert; neues Logo integrieren; NFC vorbereiten.

**Architecture:** Ein Sync-Script kopiert `frontend/` ins `www`-Root eines neuen Capacitor-Projekts `ios_app/` und injiziert die API-Basis (`https://werkzeug.b2interior.de`). `api.js` bekommt einen `apiUrl()`-Präfix-Helfer (Web: unverändert relativ), der Server einen zusätzlichen CORS-Origin. Build über Codemagic → TestFlight (BAU.OS-Infrastruktur wiederverwendet).

**Tech Stack:** Capacitor 7 (@capacitor/core, /ios, /cli), Node 22, FastAPI (unverändert), Codemagic CI, App Store Connect API.

## Global Constraints

- Repo: `/media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app` (vboxsf-Share; git-Warnung `maintenance.lock … busy` ist harmlos und zu ignorieren)
- Arbeitsbranch: `ios-app` (von `main` abzweigen, am Ende Merge in `main`)
- Python-Tests: `~/.venvs/werkzeug/bin/python -m pytest` (im Repo-Root); JS-Tests: `node --test tests/js/*.test.mjs` (im Repo-Root)
- Spec: `docs/superpowers/specs/2026-07-22-ios-app-capacitor-design.md`
- Logo-Quelle: `/media/sf_claude_project/Logo für Maschinen-Verwaltungs-App.zip` (enthält `icons/icon-{16,32,180,192,512}.png`, `icon-maskable-512.png`, `icon-transparent-512.png`)
- Live-Domain: `https://werkzeug.b2interior.de`; Server `root@62.238.47.224`, SSH-Key `~/.ssh/hetzner_werkzeug`; Deploy: `./deploy.sh --go` (vorher ohne Flag = Dry-Run); Dienst `werkzeug-app.service`
- Bundle-ID: `de.b2interior.werkzeug`; App-Name: „Werkzeug"
- Codemagic: bestehendes persönliches Konto, API-Token in `~/.codemagic_token`, **NIEMALS ein Codemagic-Team anlegen**; Developer-Portal-Integration heißt `bauos-asc-key` (kontoweit, wiederverwendbar); Apple-Keys liegen unter `/media/sf_claude_project/Apple_Keys`
- Lehren aus BAU.OS: Web-Assets ins **www-ROOT** (kein Unterordner); `artifacts:`-Globs in codemagic.yaml **relativ zum working_directory**; Signierungs-Zertifikate nur über die Codemagic-UI erzeugen (existieren bereits); ein „failed" beim ASC-Publish kann nur die externe Beta-Review betreffen
- Alle Commits enden mit `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Logo-Assets einbinden (Web-Kopfzeile + Favicons)

**Files:**
- Create: `frontend/assets/icons/` (7 PNGs aus dem ZIP)
- Modify: `frontend/js/ui.js:40-45` (logoMarkup)
- Modify: `frontend/index.html` (head: Favicon-/Touch-Icon-Links)

**Interfaces:**
- Consumes: nichts
- Produces: `logoMarkup(sizeCls)` liefert weiterhin einen HTML-String (Aufrufer `app.js` unverändert); Assets liegen unter `/static/assets/icons/…`

- [ ] **Step 1: Branch anlegen und Assets entpacken**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
git checkout -b ios-app
mkdir -p frontend/assets/icons /tmp/logo_neu
unzip -o "/media/sf_claude_project/Logo für Maschinen-Verwaltungs-App.zip" -d /tmp/logo_neu
cp /tmp/logo_neu/icons/*.png frontend/assets/icons/
ls frontend/assets/icons
```
Expected: 7 Dateien (`icon-16.png … icon-transparent-512.png`).

- [ ] **Step 2: Platzhalter-Logo ersetzen**

In `frontend/js/ui.js` die Funktion `logoMarkup` ersetzen (Kommentar mit anpassen):

```js
// Echtes App-Logo (frontend/assets/icons). Austausch weiterhin NUR hier.
export function logoMarkup(sizeCls = 'h-8 w-8 text-sm') {
  return `<img src="/static/assets/icons/icon-transparent-512.png" alt="Logo" ` +
         `class="inline-block ${sizeCls} rounded-lg">`;
}
```

- [ ] **Step 3: Favicons in index.html verlinken**

In `frontend/index.html` im `<head>` direkt nach `<title>…</title>` einfügen:

```html
  <link rel="icon" type="image/png" sizes="32x32" href="/static/assets/icons/icon-32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/static/assets/icons/icon-16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/static/assets/icons/icon-180.png">
```

- [ ] **Step 4: Lokal verifizieren**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m uvicorn backend.main:app --port 8123 &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8123/static/assets/icons/icon-transparent-512.png
curl -s http://127.0.0.1:8123/ | grep -c "apple-touch-icon"
kill %1
```
Expected: `200` und `1`.

- [ ] **Step 5: Tests und Commit**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q && node --test tests/js/*.test.mjs
git add frontend/assets frontend/js/ui.js frontend/index.html
git commit -m "feat(frontend): echtes App-Logo (Kopfzeile + Favicons)"
```
Expected: alle Tests PASS.

---

### Task 2: API-Basis-Präfix für den nativen Betrieb

**Files:**
- Create: `frontend/js/api_base.js`
- Test: `tests/js/api_base.test.mjs`
- Modify: `frontend/js/api.js` (einzige fetch-Stelle in `authFetch`)

**Interfaces:**
- Consumes: nichts
- Produces: `apiUrl(path: string): string` — gibt `globalThis.WERKZEUG_API_BASE + path` zurück, ohne gesetzte Basis den Pfad unverändert. `api.js` nutzt es intern; alle `api.get/post/…`-Aufrufer bleiben unverändert.

- [ ] **Step 1: Failing Test schreiben** (`tests/js/api_base.test.mjs`)

```js
import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl } from '../../frontend/js/api_base.js';

afterEach(() => { delete globalThis.WERKZEUG_API_BASE; });

test('ohne Basis bleibt der Pfad unverändert', () => {
  assert.equal(apiUrl('/api/me'), '/api/me');
});

test('mit Basis wird der Pfad gepräfixt', () => {
  globalThis.WERKZEUG_API_BASE = 'https://werkzeug.b2interior.de';
  assert.equal(apiUrl('/api/me'), 'https://werkzeug.b2interior.de/api/me');
});

test('Basis mit End-Slash erzeugt keinen Doppel-Slash', () => {
  globalThis.WERKZEUG_API_BASE = 'https://werkzeug.b2interior.de/';
  assert.equal(apiUrl('/api/me'), 'https://werkzeug.b2interior.de/api/me');
});
```

- [ ] **Step 2: Test läuft rot**

Run: `node --test tests/js/api_base.test.mjs`
Expected: FAIL (Modul nicht gefunden).

- [ ] **Step 3: Implementieren** (`frontend/js/api_base.js`)

```js
// API-Basis für den nativen Betrieb (Capacitor). Im Web ist die Variable
// nicht gesetzt und alle Pfade bleiben relativ (same-origin).
export function apiUrl(path) {
  const base = globalThis.WERKZEUG_API_BASE || '';
  return base ? base.replace(/\/+$/, '') + path : path;
}
```

- [ ] **Step 4: Test läuft grün**

Run: `node --test tests/js/api_base.test.mjs`
Expected: 3 PASS.

- [ ] **Step 5: api.js umstellen**

In `frontend/js/api.js`: oben `import { apiUrl } from './api_base.js';` ergänzen und in `authFetch` die Zeile

```js
    res = await fetch(path, { ...options, headers });
```
ersetzen durch
```js
    res = await fetch(apiUrl(path), { ...options, headers });
```
(`authFetch` ist die einzige fetch-Stelle; `request` und `oeffneBlobImNeuenTab` laufen darüber.)

- [ ] **Step 6: Alle Tests und Commit**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q && node --test tests/js/*.test.mjs
git add frontend/js/api_base.js frontend/js/api.js tests/js/api_base.test.mjs
git commit -m "feat(frontend): apiUrl-Präfix für nativen Betrieb (Web unverändert)"
```

---

### Task 3: Scan-Quellen-Abstraktion (NFC-Vorbereitung)

**Files:**
- Modify: `frontend/js/scanner.js` (neue Export-Funktion am Dateiende)
- Modify: `frontend/js/app.js` (Import + Aufrufstelle von `scanQr`)
- Test: `tests/js/hole_werkzeug_code.test.mjs`

**Interfaces:**
- Consumes: `scanQr(): Promise<string|null>` (bestehend in scanner.js)
- Produces: `holeWerkzeugCode(quelle?: () => Promise<string|null>): Promise<string|null>` — einzige Stelle, an der die UI einen Werkzeug-Code beschafft; NFC wird später eine alternative `quelle`.

- [ ] **Step 1: Failing Test schreiben** (`tests/js/hole_werkzeug_code.test.mjs`)

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { holeWerkzeugCode } from '../../frontend/js/scanner_quelle.js';

test('liefert den Code der übergebenen Quelle', async () => {
  assert.equal(await holeWerkzeugCode(async () => 'M-0001'), 'M-0001');
});

test('reicht null (Abbruch) durch', async () => {
  assert.equal(await holeWerkzeugCode(async () => null), null);
});
```

Hinweis: eigene Datei `scanner_quelle.js` statt `scanner.js`, weil `scanner.js` DOM-Abhängigkeiten importiert und unter `node --test` nicht ladbar ist.

- [ ] **Step 2: Test läuft rot**

Run: `node --test tests/js/hole_werkzeug_code.test.mjs`
Expected: FAIL (Modul nicht gefunden).

- [ ] **Step 3: Implementieren** (Create: `frontend/js/scanner_quelle.js`)

```js
// NFC-Vorbereitung: Die UI beschafft Werkzeug-Codes NUR über diese Funktion.
// Heute ist die einzige Quelle der Kamera-QR-Scanner (scanQr); später kommt
// NFC als alternative Quelle hinzu (Chip enthält denselben Code wie der QR).
export function holeWerkzeugCode(quelle) {
  return quelle();
}
```

- [ ] **Step 4: Test läuft grün**

Run: `node --test tests/js/hole_werkzeug_code.test.mjs`
Expected: 2 PASS.

- [ ] **Step 5: app.js umstellen**

In `frontend/js/app.js`:
- Import ergänzen: `import { holeWerkzeugCode } from './scanner_quelle.js';`
- Jede Aufrufstelle `await scanQr()` ersetzen durch `await holeWerkzeugCode(scanQr)` (der bestehende `scanQr`-Import bleibt). Fundstellen mit `grep -n "scanQr(" frontend/js/app.js` ermitteln und alle umstellen.

- [ ] **Step 6: Alle Tests und Commit**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q && node --test tests/js/*.test.mjs
git add frontend/js/scanner_quelle.js frontend/js/app.js tests/js/hole_werkzeug_code.test.mjs
git commit -m "feat(frontend): holeWerkzeugCode-Abstraktion (NFC-Vorbereitung)"
```

---

### Task 4: Web-Deploy + CORS-Origin für die App

**Files:**
- Modify: nur Server-Konfiguration (Hetzner), kein Code — die Web-Änderungen aus Task 1–3 gehen mit live

**Interfaces:**
- Consumes: Tasks 1–3 (deployte Dateien), `deploy.sh`
- Produces: Live-Server akzeptiert Origin `capacitor://localhost` (Voraussetzung für Task 5 Bundle-Check und Task 7 Geräte-Abnahme)

- [ ] **Step 1: Env-Quelle des Dienstes feststellen**

```bash
ssh -i ~/.ssh/hetzner_werkzeug root@62.238.47.224 "systemctl cat werkzeug-app.service | grep -iA2 env"
```
Erwartet: `Environment=`-Zeilen oder ein `EnvironmentFile`. `CORS_ORIGINS` wird kommagetrennt gelesen (`backend/config.py:32-38`); aktueller Wert ist die BASE_URL.

- [ ] **Step 2: CORS_ORIGINS ergänzen**

Am ermittelten Ort (Unit-Drop-in oder EnvironmentFile) setzen — bestehende BASE_URL beibehalten:

```
CORS_ORIGINS=https://werkzeug.b2interior.de,capacitor://localhost
```

Danach: `systemctl daemon-reload && systemctl restart werkzeug-app.service && systemctl is-active werkzeug-app.service` → `active`.

- [ ] **Step 3: Frontend-Änderungen deployen**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
./deploy.sh        # Dry-Run prüfen: nur frontend/-Dateien + assets
./deploy.sh --go
```

- [ ] **Step 4: Live verifizieren (Web-Regression + CORS)**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://werkzeug.b2interior.de/static/assets/icons/icon-32.png
curl -s -X OPTIONS https://werkzeug.b2interior.de/api/login \
  -H "Origin: capacitor://localhost" -H "Access-Control-Request-Method: POST" \
  -D - -o /dev/null | grep -i access-control-allow-origin
```
Expected: `200` und `access-control-allow-origin: capacitor://localhost`.
Zusätzlich Web-Login headless prüfen (Chrome aus dem puppeteer-Cache der VM): Seite lädt, Login-Formular erscheint, Logo-Bild wird geladen (kein 404 in der Konsole).

- [ ] **Step 5: Commit (nur Doku, falls Runbook-Notiz nötig) — sonst kein Commit**

In `README.md` unter Deploy-Hinweisen eine Zeile ergänzen: „CORS_ORIGINS auf dem Server muss `capacitor://localhost` enthalten (iOS-App)." Dann:

```bash
git add README.md && git commit -m "docs: CORS-Hinweis für iOS-App im Deploy-Runbook"
```

---

### Task 5: Capacitor-Projekt `ios_app/` + Sync-Script + Bundle-Check

**Files:**
- Create: `ios_app/package.json`, `ios_app/capacitor.config.json`, `ios_app/scripts/sync-assets.mjs`, `ios_app/.gitignore`, `ios_app/resources/AppIcon-1024.png`
- Create (generiert): `ios_app/ios/` (via `npx cap add ios`, wird committet)
- Modify (generiert): `ios_app/ios/App/App/Info.plist` (Kamera-Text), `ios_app/ios/App/App/Assets.xcassets/AppIcon.appiconset/` (Icon)

**Interfaces:**
- Consumes: `frontend/` (Tasks 1–3), Live-API mit CORS (Task 4)
- Produces: `node ios_app/scripts/sync-assets.mjs` erzeugt lauffähiges `ios_app/www/`; Xcode-Projekt für Task 6 (Codemagic baut `ios_app/ios/App/App.xcworkspace`, Scheme `App`)

- [ ] **Step 1: Projektgerüst anlegen**

`ios_app/package.json`:
```json
{
  "name": "werkzeug-native",
  "version": "1.0.0",
  "private": true,
  "description": "Werkzeug-Ausleihe native iOS-Huelle (Capacitor, online-only) um frontend/",
  "type": "module",
  "scripts": { "sync-assets": "node scripts/sync-assets.mjs" },
  "dependencies": { "@capacitor/core": "^7.0.0", "@capacitor/ios": "^7.0.0" },
  "devDependencies": { "@capacitor/cli": "^7.0.0" }
}
```

`ios_app/capacitor.config.json`:
```json
{
  "appId": "de.b2interior.werkzeug",
  "appName": "Werkzeug",
  "webDir": "www",
  "server": { "allowNavigation": ["werkzeug.b2interior.de"] }
}
```

`ios_app/.gitignore`:
```
node_modules/
www/
ios/App/Pods/
ios/App/output/
```

Dann: `cd ios_app && npm install` (Node aus `~/.local`).

- [ ] **Step 2: sync-assets.mjs schreiben** (`ios_app/scripts/sync-assets.mjs`)

Muster BAU.OS (`/home/b2/bauos-native/bauos_installer/app_native/scripts/sync-assets.mjs`), angepasst:

```js
#!/usr/bin/env node
// Bündelt frontend/ ins Capacitor-www (www-ROOT, Lehre BAU.OS) und macht es nativ:
// 1. Kopie von frontend/ (ohne package.json/node_modules)
// 2. "/static/-Pfade → relative Pfade (Drift-Guard: exit 1 wenn nicht gefunden)
// 3. app-config.js mit WERKZEUG_API_BASE erzeugen + in index.html einbinden
import { cpSync, rmSync, mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(here, '..', '..', 'frontend');
const OUT = resolve(here, '..', 'www');
const API_BASE = 'https://werkzeug.b2interior.de';

if (!existsSync(join(SRC, 'index.html'))) {
  console.error(`sync-assets: Quelle nicht gefunden: ${SRC}`);
  process.exit(1);
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
cpSync(SRC, OUT, {
  recursive: true,
  filter: (src) => !['package.json', 'node_modules'].includes(basename(src)),
});

// index.html: /static/-Präfixe entfernen + app-config.js einbinden
{
  const p = join(OUT, 'index.html');
  let html = readFileSync(p, 'utf8');
  if (!html.includes('"/static/')) {
    console.error('sync-assets: DRIFT — "/static/" nicht in index.html (Pfad-Struktur geändert?)');
    process.exit(1);
  }
  html = html.replaceAll('"/static/', '"');
  if (!html.includes('<script type="module" src="js/app.js">')) {
    console.error('sync-assets: DRIFT — app.js-Script-Tag nach Rewrite nicht gefunden');
    process.exit(1);
  }
  html = html.replace('<script type="module" src="js/app.js">',
    '<script src="app-config.js"></script>\n  <script type="module" src="js/app.js">');
  writeFileSync(p, html);
}

// Logo-Pfad in ui.js relativieren (nutzt /static/assets/…)
{
  const p = join(OUT, 'js', 'ui.js');
  let js = readFileSync(p, 'utf8');
  if (!js.includes('/static/assets/')) {
    console.error('sync-assets: DRIFT — /static/assets/ nicht in ui.js gefunden');
    process.exit(1);
  }
  js = js.replaceAll('/static/assets/', 'assets/');
  writeFileSync(p, js);
}

writeFileSync(join(OUT, 'app-config.js'),
  `window.WERKZEUG_API_BASE = '${API_BASE}';\n`);

console.log(`sync-assets: ok → ${OUT}`);
```

Danach Restprüfung, dass keine weiteren absoluten `/static/`-Referenzen in `frontend/js/` existieren:
```bash
grep -rn '"/static/' frontend/js || true
```
Jeder weitere Treffer bekommt einen eigenen Rewrite mit Drift-Guard nach obigem Muster.

- [ ] **Step 3: iOS-Plattform erzeugen**

```bash
cd ios_app && npm run sync-assets && npx cap add ios
```
Expected: `ios/App/…` wird erzeugt (Xcode-Warnungen auf Linux sind ok; `pod install` läuft erst auf Codemagic). Danach in `ios/App/App/Info.plist` vor `</dict>` einfügen:

```xml
	<key>NSCameraUsageDescription</key>
	<string>Die Kamera wird zum Scannen der QR-Codes an den Werkzeugen benötigt.</string>
```

- [ ] **Step 4: App-Icon (1024) erzeugen und einsetzen**

```bash
~/.venvs/werkzeug/bin/python -c "import PIL" 2>/dev/null || ~/.venvs/werkzeug/bin/pip install pillow
~/.venvs/werkzeug/bin/python - <<'EOF'
from PIL import Image
img = Image.open('frontend/assets/icons/icon-maskable-512.png').convert('RGB')
img.resize((1024, 1024), Image.LANCZOS).save('ios_app/resources/AppIcon-1024.png')
EOF
```
(Pfad relativ zum Repo-Root; `ios_app/resources/` vorher anlegen.) Dann in
`ios_app/ios/App/App/Assets.xcassets/AppIcon.appiconset/Contents.json` den referenzierten
Dateinamen nachschlagen und die dortige PNG durch `AppIcon-1024.png` ersetzen (Datei
kopieren und `Contents.json`-Eintrag auf den Namen der Kopie belassen bzw. anpassen).
Verifizieren: referenzierte Datei existiert und ist 1024×1024 (`file …`).

- [ ] **Step 5: Bundle-Check headless gegen Live-API**

```bash
cd ios_app && python3 -m http.server 8321 --directory www &
sleep 1
```
Headless-Chrome (puppeteer-Cache der VM) auf `http://127.0.0.1:8321` richten:
Login-Maske erscheint, Login mit gültigem Nutzer gegen `https://werkzeug.b2interior.de`
funktioniert (beweist `apiUrl` + CORS; Origin `http://127.0.0.1:8321` ggf. temporär
zusätzlich in CORS_ORIGINS auf dem Server aufnehmen und danach wieder entfernen),
keine 404 in der Konsole. Danach `kill %1`.

- [ ] **Step 6: Commit**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
git add ios_app
git commit -m "feat(ios): Capacitor-Projekt mit Frontend-Bündelung und App-Icon"
```

---

### Task 6: Codemagic-Workflow + App Store Connect

**Files:**
- Create: `codemagic.yaml` (Repo-Root)

**Interfaces:**
- Consumes: `ios_app/` aus Task 5; Codemagic-Konto/Token (`~/.codemagic_token`); ASC-Key-Integration `bauos-asc-key`; Apple-Keys unter `/media/sf_claude_project/Apple_Keys`
- Produces: Codemagic-App für `btwointerior/werkzeug-app` mit Workflow `ios-native`; ASC-App „Werkzeug" (Bundle-ID `de.b2interior.werkzeug`) mit interner TestFlight-Gruppe

- [ ] **Step 1: codemagic.yaml schreiben** (Muster BAU.OS, Globs relativ zum working_directory!)

```yaml
# CI-Build der nativen iOS-App (Werkzeug-Ausleihe). Läuft auf Codemagic.
# Nutzt die bestehende Developer-Portal-Integration "bauos-asc-key" (kontoweit).
# Trigger: manuell über die Codemagic-UI oder Git-Tag "app-v*".
workflows:
  ios-native:
    name: Werkzeug iOS (TestFlight)
    instance_type: mac_mini_m2
    max_build_duration: 45
    working_directory: ios_app
    integrations:
      app_store_connect: bauos-asc-key
    environment:
      ios_signing:
        distribution_type: app_store
        bundle_identifier: de.b2interior.werkzeug
      node: "22"
      xcode: latest
    triggering:
      events:
        - tag
      tag_patterns:
        - pattern: 'app-v*'
    scripts:
      - name: npm-Abhängigkeiten
        script: npm ci
      - name: Web-Assets bündeln
        script: npm run sync-assets
      - name: Capacitor sync (www -> Xcode-Projekt, pod install)
        script: npx cap sync ios
      - name: Signierungs-Profile anwenden
        script: xcode-project use-profiles
      - name: Build-Nummer setzen
        script: cd ios/App && agvtool new-version -all $BUILD_NUMBER
      - name: IPA bauen
        script: |
          xcode-project build-ipa \
            --workspace ios/App/App.xcworkspace \
            --scheme App
    artifacts:
      - build/ios/ipa/*.ipa
      - /tmp/xcodebuild_logs/*.log
    publishing:
      app_store_connect:
        auth: integration
        submit_to_testflight: true
```

```bash
git add codemagic.yaml && git commit -m "ci: Codemagic-Workflow iOS/TestFlight"
```

- [ ] **Step 2: Bundle-ID + ASC-App anlegen (App Store Connect API)**

Mit dem ASC-API-Key aus `/media/sf_claude_project/Apple_Keys` (Key-ID/Issuer-ID liegen dort; JWT per Python `pyjwt` + `cryptography` aus dem Werkzeug-venv, bei Bedarf nachinstallieren):
1. `POST https://api.appstoreconnect.apple.com/v1/bundleIds` — `{"data":{"type":"bundleIds","attributes":{"identifier":"de.b2interior.werkzeug","name":"Werkzeug","platform":"IOS"}}}`
2. `POST /v1/apps` ist nicht verfügbar — App-Anlage in ASC per API heißt: `POST /v1/apps` existiert nicht öffentlich → App in der ASC-UI anlegen lassen **oder** (wie bei BAU.OS erprobt) den Weg über die UI gehen: Name „Werkzeug", Sprache Deutsch, Bundle-ID `de.b2interior.werkzeug`, SKU `werkzeug-app`. Falls UI nötig: Nutzer bitten, sonst selbst per bestehender Session.
3. Interne TestFlight-Gruppe „Team" anlegen und `fb@b2interior.de` (+ ggf. weitere Mitarbeiter-Apple-IDs, beim Nutzer erfragen) als internen Tester einladen.
4. Export-Compliance vorab setzen (kein proprietäres Encryption; wie bei BAU.OS).

- [ ] **Step 3: Codemagic-App anlegen und verifizieren**

```bash
TOKEN=$(cat ~/.codemagic_token)
curl -s -X POST https://api.codemagic.io/apps \
  -H "x-auth-token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"repositoryUrl": "git@github.com:btwointerior/werkzeug-app.git"}'
```
Expected: JSON mit neuer `_id` (im Personal Account, KEIN Team). Bei SSH-Zugriffsproblemen die bestehende GitHub-App-Integration von Codemagic nutzen (wie bei bauos, ggf. über UI verknüpfen). App-ID notieren.

- [ ] **Step 4: Commit-Stand pushen**

```bash
git push -u origin ios-app
```

---

### Task 7: Erster TestFlight-Build + Abnahme

**Files:** keine neuen — Build/Verifikation

**Interfaces:**
- Consumes: Tasks 5–6 (Projekt, Workflow, ASC-App)
- Produces: installierbare TestFlight-Build; Merge nach `main`

- [ ] **Step 1: Branch nach main mergen und taggen**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
git checkout main && git merge --no-ff ios-app -m "merge: iOS-App (Capacitor) + Logo + NFC-Vorbereitung"
git tag app-v1.0.0 && git push origin main app-v1.0.0
```

- [ ] **Step 2: Build überwachen**

Tag löst den Codemagic-Build aus; Status per API pollen (Abstand ≥ 4 min):

```bash
TOKEN=$(cat ~/.codemagic_token)
curl -s -H "x-auth-token: $TOKEN" "https://api.codemagic.io/builds?appId=<APP_ID>" | head -c 2000
```
Expected: Build `successful`, IPA-Artefakt vorhanden, TestFlight-Upload ok („failed" nur beim externen-Beta-Schritt ist ok — Lehre BAU.OS). Bei Fehlern: Logs aus dem Build ziehen, Ursache beheben, neuen Tag `app-v1.0.1` setzen.

- [ ] **Step 3: Geräte-Abnahme durch den Nutzer (Blocker melden, dann warten)**

Checkliste an den Nutzer:
1. TestFlight-Einladung „Werkzeug" annehmen, App installieren
2. App-Start: Login-Maske mit neuem Logo erscheint
3. Login + Werkzeug ausleihen/zurückgeben
4. QR-Scan mit Kamera (Kamera-Berechtigungsdialog mit deutschem Text)
5. Bekannte Einschränkung prüfen: PDF-/Blob-Öffnen (falls in der App genutzt) — Verhalten notieren

- [ ] **Step 4: Memory aktualisieren**

Nach bestandener Abnahme `werkzeug-app`-Memory um iOS-App-Stand ergänzen (Codemagic-App-ID, ASC-App, Tag-Konvention `app-v*`, CORS-Origin, Logo integriert).

---

## Self-Review (erledigt)

- Spec-Abdeckung: Logo/Icon (T1, T5.4), apiUrl (T2), NFC-Vorbereitung (T3), CORS (T4), Bündelung www-Root + Drift-Guards (T5), Codemagic/TestFlight (T6–T7), Tests/Abnahme (in jedem Task + T7.3). Keine Lücken.
- Platzhalter: keine.
- Konsistenz: `apiUrl`, `holeWerkzeugCode`, Pfade und Bundle-ID in allen Tasks identisch; `scanner_quelle.js` einheitlich in T3.
