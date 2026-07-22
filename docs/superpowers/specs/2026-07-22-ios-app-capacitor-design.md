# Design: Werkzeugverwaltung als iOS-App (Capacitor, online-only)

**Datum:** 2026-07-22
**Status:** Entwurf zur Freigabe

## Ziel

Die bestehende Werkzeug-Ausleih-Webapp (FastAPI + statisches Frontend, live auf
https://werkzeug.b2interior.de) soll zusätzlich als echte iOS-App verfügbar sein.

- **Nutzerkreis:** nur eigene Mitarbeiter (nicht öffentlich)
- **Verteilung:** TestFlight (interne Gruppe) jetzt, Unlisted App Store später
- **Offline:** nicht erforderlich — die App arbeitet online gegen den Hetzner-Server
- **Webapp:** bleibt unverändert für alle Nicht-iOS-Nutzer bestehen; beide teilen
  denselben Server und dieselben Daten

## Gewählter Ansatz

Capacitor-App mit **gebündeltem Frontend** (Variante 1): Das bestehende statische
Frontend (`frontend/`) wird beim Build in das `www`-Root des Capacitor-Projekts
kopiert und spricht per HTTPS mit der Live-API. Keine reine Remote-Hülle (Apple-
Review-Risiko, Fehlerseite ohne Netz), keine Offline-Sync-Engine (nicht benötigt).

Wiederverwendet wird die komplette BAU.OS-Stufe-2-Infrastruktur: Apple-Developer-
Konto, Codemagic-Konto (bestehendes persönliches Konto, **kein neues Team**),
Zertifikat/Profil-Workflow (nur per Codemagic-UI generieren), TestFlight-Ablauf.

## Architektur

```
werkzeug-app (GitHub btwointerior/werkzeug-app, existiert)
├── backend/          FastAPI – unverändert bis auf CORS-Erweiterung
├── frontend/         Single Source of Truth der UI (Web + App)
│   └── assets/       NEU: Logo (UI) + App-Icon-Quelle
├── ios_app/          NEU: Capacitor-Projekt
│   ├── www/          Build-Artefakt: Kopie von frontend/ ins www-ROOT
│   │                 (Lehre BAU.OS: Capacitor-Router kennt keine
│   │                 Verzeichnis-Indizes)
│   ├── capacitor.config.*  App-ID, iOS-Konfiguration
│   └── sync.sh       kopiert frontend/ → www/ + injiziert API-Basis
└── codemagic.yaml    NEU: iOS-Build → TestFlight (artifacts-Globs relativ
                      zum working_directory – Lehre BAU.OS ded18f8)
```

### Komponenten und Entscheidungen

**1. Frontend-Bündelung (`ios_app/sync.sh`)**
Kopiert `frontend/` nach `ios_app/www/` (www-Root, kein Unterverzeichnis).
Es gibt genau eine Frontend-Codebasis; die App ist immer eine Kopie davon.

**2. API-Basis-URL**
Das Frontend ruft die API heute mit relativen Pfaden auf (`api.js`). Neu:
`api.js` prefixt alle Pfade mit `window.WERKZEUG_API_BASE || ''`.
- Web: Variable nicht gesetzt → relative Pfade, Verhalten unverändert.
- App: `sync.sh` legt eine kleine `app-config.js` ins www-Root, die
  `window.WERKZEUG_API_BASE = "https://werkzeug.b2interior.de"` setzt und
  nur in der App-Kopie der `index.html` eingebunden wird.

**3. Auth**
Bearer-Token in `localStorage` (bestehend) — funktioniert in der Capacitor-
WebView unverändert, keine Cookie-Problematik. Keine Änderung nötig.

**4. CORS (Server)**
Die App läuft unter Origin `capacitor://localhost`. Dieser Origin wird in
`CORS_ORIGINS` der Server-Umgebung ergänzt (env-Variable auf Hetzner,
kein Code-Default für Prod nötig). Deploy-Schritt dokumentieren.

**5. QR-Scanner (Kamera)**
`scanner.js` nutzt `getUserMedia` — in WKWebView ab iOS 14.3 verfügbar.
Nötig: `NSCameraUsageDescription` in der Info.plist, ggf.
`allowsInlineMediaPlayback`. Funktion wird auf dem Gerät (TestFlight)
explizit abgenommen; Fallback bleibt die manuelle Eingabe wie im Web.

**6. Logo & App-Icon**
Ablageort für das neue Logo: **`frontend/assets/`**
- `frontend/assets/logo.svg` (oder `.png`, möglichst hochauflösend) → ersetzt
  den Platzhalter in `ui.js::logoMarkup()` (einzige Austauschstelle, im Web
  erreichbar unter `/static/assets/…`).
- `frontend/assets/app-icon-1024.png` (1024×1024, ohne Transparenz, ohne
  abgerundete Ecken) → Quelle für das iOS-App-Icon.
Liegt nur eine Datei vor, wird das Icon daraus abgeleitet (Lime `#d4f000`
auf Nachtblau `#0b0f1a`). Bis dahin startet die App mit einem aus den
App-Farben generierten Interims-Icon.

**7. Build & Verteilung (Codemagic)**
- Neue Bundle-ID (z. B. `de.b2interior.werkzeug`), neue App in App Store
  Connect, bestehender ASC-API-Key.
- `codemagic.yaml` analog BAU.OS: sync.sh → `cap sync ios` → Archiv →
  TestFlight-Upload; Export-Compliance-Flag setzen.
- Interne TestFlight-Gruppe mit den Mitarbeiter-Apple-IDs.

## Fehlerbehandlung

- Ohne Netz zeigt die App die bestehende Fehlermeldung aus `api.js`
  („Netzwerkfehler. Server nicht erreichbar.") — akzeptiert, da online-only.
- 401-Handling (Token abgelaufen) führt wie im Web zum Login — unverändert.

## Tests & Abnahme

1. **Bestehende Suite:** pytest-Suite muss unverändert grün bleiben
   (API-Basis-Änderung in `api.js` ist rein additiv).
2. **Web-Regression:** Headless-Check gegen die Live-Webapp nach Deploy der
   CORS-/api.js-Änderung (Login + Kernflow), da Web und App dieselben
   Dateien teilen.
3. **Bundle-Check lokal:** `ios_app/www/` headless laden → Login gegen
   Live-API funktioniert (beweist API-Basis + CORS vor dem ersten iOS-Build).
4. **Geräte-Abnahme (User, TestFlight):** App-Start, Login, Ausleihe/Rückgabe,
   QR-Scan mit Kamera.

## Ausdrücklich außerhalb des Umfangs

- Offline-Betrieb / Sync-Engine
- Öffentlicher App-Store-Auftritt (nur TestFlight, später Unlisted)
- Android-App
- Änderungen an Funktionsumfang oder Design der Webapp
