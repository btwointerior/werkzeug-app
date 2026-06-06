# Design-Overhaul „Signal“ (Dark + Lime) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der App ein durchgängig dunkles, markentaugliches Erscheinungsbild („Signal“: dunkler Grund + Lime-Akzent) geben — rein optisch, ohne Änderung an Screens, Navigation, Abläufen oder Backend.

**Architecture:** Optik wird zentralisiert. Ein Tailwind-CDN-Theme (`index.html`) definiert benannte Farb-Tokens; die geteilten UI-Bausteine (`ui.js`) und das Chrome (`app.js`) werden auf diese Tokens umgestellt; danach werden die 8 Views mit einer festen Klassen-Mapping-Tabelle nachgezogen. Kein Build-Step, keine neuen Abhängigkeiten.

**Tech Stack:** Tailwind via CDN, Vanilla-JS-ES-Module, FastAPI (statisches Ausliefern), pytest (Regressionsnetz).

**Spec:** `docs/superpowers/specs/2026-06-06-design-overhaul-design.md`

---

## Verifikations-Grundsätze (für ALLE Tasks)

Es gibt keine Frontend-Unit-Tests. Pro Task gilt:
- **Regression:** `~/.venvs/werkzeug/bin/python -m pytest -q` muss grün bleiben (32 passed). Erwartet: keine funktionale Änderung → niemals rot.
- **Manuell:** App starten und betroffene Seite(n) im Browser prüfen.

**App lokal starten (einmal pro Sitzung, im Hintergrund):**
```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m uvicorn backend.main:app --reload --port 8000
```
Dann im Browser `http://localhost:8000`. Demo-Login siehe `backend/seed.py`. Vorhandene Daten: 4 Maschinen, 7 Zubehör, 3 Benutzer.

**Manuelle Prüfpunkte je Screen:** Lesbarkeit (heller Text auf dunklem Grund), korrekte Status-Farben, keine versehentlich hellen Restflächen (weiße Kästen/Ränder), Touch-Ziele ≥ 48px unverändert.

---

## Datei-Übersicht

| Datei | Verantwortung | Aktion |
|-------|---------------|--------|
| `frontend/index.html` | Tailwind-Theme-Tokens, dunkler Body, theme-color | Modify |
| `frontend/js/ui.js` | Geteilte Bausteine + `logoMarkup()` | Modify |
| `frontend/js/app.js` | Topbar, Bottom-Nav, 404/Fehler-Ansicht | Modify |
| `frontend/js/views/login.js` | Klassen-Mapping | Modify |
| `frontend/js/views/meine.js` | Klassen-Mapping | Modify |
| `frontend/js/views/admin_maschinen.js` | Klassen-Mapping | Modify |
| `frontend/js/views/admin_benutzer.js` | Klassen-Mapping | Modify |
| `frontend/js/views/admin_dashboard.js` | Klassen-Mapping + Status-Kachelfarben | Modify |
| `frontend/js/views/admin_historie.js` | Klassen-Mapping + blaues Badge | Modify |
| `frontend/js/views/maschine.js` | Klassen-Mapping + blaue Info-/Auswahl-Flächen | Modify |
| `frontend/js/views/admin_maschine_form.js` | Klassen-Mapping + blaue Auswahl-/Button-Flächen | Modify |

---

## Standard-Klassen-Mapping (zentrale Referenz)

Diese Tabelle gilt für **alle** Views (Tasks 4–7). Hell → Token:

| Alt (hell) | Neu (Token) |
|------------|-------------|
| `bg-white` | `bg-surface` |
| `bg-slate-50` | `bg-bg` |
| `bg-slate-100` | `bg-surface-2` |
| `hover:bg-slate-50` | `hover:bg-surface-2` |
| `hover:bg-slate-100` | `hover:bg-surface-2` |
| `text-slate-900` | `text-txt` |
| `text-slate-800` | `text-txt` |
| `text-slate-700` | `text-txt-2` |
| `text-slate-600` | `text-muted` |
| `text-slate-500` | `text-muted` |
| `text-slate-400` | `text-muted-2` |
| `border-slate-200` | `border-border` |
| `border-slate-300` | `border-border` |

Blaue Flächen (Akzent/Auswahl) werden **nicht** über diese Tabelle, sondern pro Task einzeln behandelt (Tasks 6 & 7).

---

## Task 0: Branch & Baseline

**Files:** keine Änderung.

- [ ] **Step 1: Auf dem Feature-Branch sein**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
git rev-parse --abbrev-ref HEAD
```
Erwartet: `feature/design-overhaul` (existiert bereits inkl. committeter Spec). Falls nicht: `git checkout feature/design-overhaul`.

- [ ] **Step 2: Baseline-Tests grün**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`.

---

## Task 1: Tailwind-Theme-Tokens (`index.html`)

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Theme-Config direkt nach dem Tailwind-CDN-Script einfügen**

Ersetze die Zeile
```html
  <script src="https://cdn.tailwindcss.com"></script>
```
durch:
```html
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            bg: '#0b0f1a',
            surface: '#151b2b',
            'surface-2': '#1e2740',
            border: '#1e2740',
            accent: '#d4f000',
            'accent-ink': '#0b0f1a',
            txt: '#ffffff',
            'txt-2': '#cbd5e1',
            muted: '#94a3b8',
            'muted-2': '#64748b',
            ok: '#34d399',
            lent: '#60a5fa',
            broken: '#f87171',
            maint: '#fbbf24',
          },
        },
      },
    };
  </script>
```

- [ ] **Step 2: theme-color-Meta auf Dunkel setzen**

Ersetze
```html
  <meta name="theme-color" content="#2563eb">
```
durch
```html
  <meta name="theme-color" content="#0b0f1a">
```

- [ ] **Step 3: Body auf dunkle Tokens umstellen**

Ersetze
```html
<body class="bg-slate-50 text-slate-900 min-h-screen">
```
durch
```html
<body class="bg-bg text-txt-2 min-h-screen">
```

- [ ] **Step 4: Regression + manueller Smoke-Test**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser neu laden: Hintergrund ist jetzt dunkel (Inhalte sind teils noch hell — wird in den Folge-Tasks behoben). `bg-accent`/`text-txt`-Klassen dürfen keine Konsolenfehler werfen.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "Design: Tailwind-Theme-Tokens + dunkler Body (Signal/Dark+Lime)"
```

---

## Task 2: Geteilte UI-Bausteine (`ui.js`)

**Files:**
- Modify: `frontend/js/ui.js`

- [ ] **Step 1: `btnClasses` neu einfärben**

Ersetze die komplette Funktion `btnClasses` durch:
```js
export function btnClasses(variant = 'primary') {
  const base =
    'inline-flex items-center justify-center min-h-[48px] px-4 rounded-xl ' +
    'font-semibold transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    primary:   'bg-accent text-accent-ink hover:brightness-95',
    secondary: 'bg-surface-2 text-txt-2 hover:brightness-110',
    success:   'bg-ok text-accent-ink hover:brightness-95',
    warning:   'bg-maint text-accent-ink hover:brightness-95',
    danger:    'bg-broken text-accent-ink hover:brightness-95',
    ghost:     'bg-transparent text-txt-2 hover:bg-surface-2',
  };
  return `${base} ${variants[variant] || variants.primary}`;
}
```

- [ ] **Step 2: `logoMarkup`-Helfer ergänzen (für späteren Logo-Austausch an einer Stelle)**

Füge direkt nach `btnClasses` ein:
```js
// Platzhalter-Logo. Späterer Austausch gegen echtes B2-Interior-Logo NUR hier.
export function logoMarkup(sizeCls = 'h-8 w-8 text-sm') {
  return `<span class="inline-flex items-center justify-center ${sizeCls} rounded-lg ` +
         `bg-accent text-accent-ink font-extrabold tracking-tight">B2</span>`;
}
```

- [ ] **Step 3: `TOAST_VARIANTS` + `toast`-Textfarbe umstellen**

Ersetze
```js
const TOAST_VARIANTS = {
  success: 'bg-emerald-600',
  error: 'bg-rose-600',
  info: 'bg-slate-800',
};
```
durch
```js
const TOAST_VARIANTS = {
  success: 'bg-ok text-accent-ink',
  error: 'bg-broken text-accent-ink',
  info: 'bg-surface-2 text-txt',
};
```
und in der Funktion `toast` ersetze die Klassenzeile
```js
  el.className =
    `${TOAST_VARIANTS[typ] || TOAST_VARIANTS.info} text-white rounded-lg shadow-lg ` +
    'px-4 py-3 text-base mb-2 max-w-sm pointer-events-auto';
```
durch (das `text-white` entfällt, Farbe kommt aus der Variante; Rundung `rounded-xl`):
```js
  el.className =
    `${TOAST_VARIANTS[typ] || TOAST_VARIANTS.info} rounded-xl shadow-lg ` +
    'px-4 py-3 text-base mb-2 max-w-sm pointer-events-auto';
```

- [ ] **Step 4: `modal` auf dunkle Flächen umstellen**

In `modal`: ersetze die `card`-Klassen
```js
    card.className =
      'bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col';
```
durch
```js
    card.className =
      'bg-surface border border-border rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col';
```
ersetze die `header`-Klassen
```js
    header.className = 'px-5 py-4 border-b border-slate-200';
    header.innerHTML = `<h2 class="text-lg font-semibold text-slate-900">${escapeHtml(titel)}</h2>`;
```
durch
```js
    header.className = 'px-5 py-4 border-b border-border';
    header.innerHTML = `<h2 class="text-lg font-semibold text-txt">${escapeHtml(titel)}</h2>`;
```
und ersetze die `footer`-Klassen
```js
    footer.className =
      'px-5 py-4 border-t border-slate-200 flex flex-row-reverse gap-2 flex-shrink-0';
```
durch
```js
    footer.className =
      'px-5 py-4 border-t border-border flex flex-row-reverse gap-2 flex-shrink-0';
```

- [ ] **Step 5: `confirmDialog`-Text aufhellen**

Ersetze
```js
    body: `<p class="text-slate-700">${escapeHtml(text)}</p>`,
```
durch
```js
    body: `<p class="text-txt-2">${escapeHtml(text)}</p>`,
```

- [ ] **Step 6: `statusBadge` neu (Chip dunkel, Status-Farbe als Text + Punkt)**

Ersetze die komplette Funktion `statusBadge` durch:
```js
export function statusBadge(status) {
  const map = {
    verfuegbar:  { text: 'Verfügbar',   cls: 'text-ok' },
    ausgeliehen: { text: 'Ausgeliehen', cls: 'text-lent' },
    defekt:      { text: 'Defekt',      cls: 'text-broken' },
    wartung:     { text: 'In Wartung',  cls: 'text-maint' },
  };
  const m = map[status] || { text: status, cls: 'text-muted' };
  return `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold bg-surface-2 ${m.cls}">` +
         `<span class="text-[8px] leading-none">●</span>${m.text}</span>`;
}
```

- [ ] **Step 7: `spinner` + `leerZustand` umfärben**

Ersetze in `spinner`
```js
    '<div class="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full"></div>' +
```
durch
```js
    '<div class="animate-spin h-10 w-10 border-4 border-accent border-t-transparent rounded-full"></div>' +
```
und ersetze `leerZustand`
```js
  return `<div class="text-center py-12 text-slate-500">${escapeHtml(text)}</div>`;
```
durch
```js
  return `<div class="text-center py-12 text-muted">${escapeHtml(text)}</div>`;
```

- [ ] **Step 8: Regression + manueller Check**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser: einen beliebigen Button, ein Modal (z.B. „Code eingeben“) und einen Status-Badge prüfen — Lime-Button mit dunklem Text, Modal dunkel, Badge dunkler Chip mit farbigem Punkt.

- [ ] **Step 9: Commit**

```bash
git add frontend/js/ui.js
git commit -m "Design: geteilte UI-Bausteine auf Dark+Lime + logoMarkup"
```

---

## Task 3: Chrome — Topbar, Bottom-Nav, Fehleransicht (`app.js`)

**Files:**
- Modify: `frontend/js/app.js`

- [ ] **Step 1: `logoMarkup` importieren**

Ersetze
```js
import { btnClasses, escapeHtml, modal, toast } from './ui.js';
```
durch
```js
import { btnClasses, escapeHtml, logoMarkup, modal, toast } from './ui.js';
```

- [ ] **Step 2: Topbar dunkel + Logo**

Ersetze in `renderChrome` den Block
```js
  topbar.innerHTML = `
    <div class="max-w-3xl mx-auto px-4 h-14 flex items-center justify-between">
      <div class="font-semibold text-slate-900">Werkzeug-Ausleihe</div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-slate-600 hidden sm:inline">${escapeHtml(state.benutzer.voller_name)}</span>
        <button id="btn-logout" class="${btnClasses('ghost')} px-3 min-h-[40px] text-sm">Abmelden</button>
      </div>
    </div>`;
```
durch
```js
  topbar.innerHTML = `
    <div class="max-w-3xl mx-auto px-4 h-14 flex items-center justify-between">
      <div class="flex items-center gap-2">
        ${logoMarkup('h-7 w-7 text-xs')}
        <span class="font-semibold text-txt">Werkzeug-Ausleihe</span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-muted hidden sm:inline">${escapeHtml(state.benutzer.voller_name)}</span>
        <button id="btn-logout" class="${btnClasses('ghost')} px-3 min-h-[40px] text-sm">Abmelden</button>
      </div>
    </div>`;
```
und ersetze die Topbar-Container-Klassenzeile
```js
  topbar.innerHTML = `
```
ist davor — die Container-Klasse steht im HTML (`index.html`, `#topbar`) und enthält bereits `bg-white border-b border-slate-200`. **Achtung:** Diese steht in `index.html`. Ersetze dort die Zeile
```html
  <header id="topbar" class="hidden sticky top-0 z-40 bg-white border-b border-slate-200"></header>
```
durch
```html
  <header id="topbar" class="hidden sticky top-0 z-40 bg-bg border-b border-border"></header>
```

- [ ] **Step 3: Bottom-Nav dunkel + aktiver Lime-Zustand**

Ersetze in `renderChrome` den Bottom-Nav-Block
```js
  bottomnav.innerHTML = `
    <div class="max-w-3xl mx-auto h-16 border-t border-slate-200 bg-white grid"
         style="grid-template-columns: repeat(${links.length}, minmax(0, 1fr));">
      ${links.map((l, i) => `
        <button data-i="${i}" class="flex flex-col items-center justify-center text-xs gap-1 text-slate-700 hover:bg-slate-50 active:bg-slate-100">
          <span class="text-xl leading-none">${l.icon}</span>
          <span>${l.label}</span>
        </button>`).join('')}
    </div>`;
```
durch
```js
  bottomnav.innerHTML = `
    <div class="max-w-3xl mx-auto h-16 border-t border-border bg-bg grid"
         style="grid-template-columns: repeat(${links.length}, minmax(0, 1fr));">
      ${links.map((l, i) => `
        <button data-i="${i}" class="flex flex-col items-center justify-center text-xs gap-1 text-muted hover:bg-surface-2 active:bg-surface-2">
          <span class="text-xl leading-none">${l.icon}</span>
          <span>${l.label}</span>
        </button>`).join('')}
    </div>`;
```
*(Hinweis: Eine echte „aktiv = Lime“-Hervorhebung pro Route ist nicht im Scope — die bestehende Nav kennt keinen Aktiv-Status. Belassen wie hier; Hover/Active in `surface-2`.)*

- [ ] **Step 4: 404-Ansicht aufhellen**

Ersetze in `route()` den 404-Block
```js
    document.getElementById('app').innerHTML = `
      <main class="max-w-md mx-auto pt-16 px-4 text-center">
        <h1 class="text-xl font-semibold text-slate-900 mb-2">Seite nicht gefunden</h1>
        <a href="#/" class="text-blue-600 underline">Zur Startseite</a>
      </main>`;
```
durch
```js
    document.getElementById('app').innerHTML = `
      <main class="max-w-md mx-auto pt-16 px-4 text-center">
        <h1 class="text-xl font-semibold text-txt mb-2">Seite nicht gefunden</h1>
        <a href="#/" class="text-accent underline">Zur Startseite</a>
      </main>`;
```
*(Der Catch-Fehlerblock mit `text-rose-600` darf bleiben — Rot auf Dunkel ist gut lesbar.)*

- [ ] **Step 5: Regression + manueller Check**

```bash
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser: einloggen → Topbar dunkel mit B2-Logo, Bottom-Nav dunkel. Ungültige URL (`#/xxx`) → 404 dunkel.

- [ ] **Step 6: Commit**

```bash
git add frontend/js/app.js frontend/index.html
git commit -m "Design: Chrome (Topbar/Bottom-Nav/404) auf Dark+Lime + Logo"
```

---

## Task 4: Einfache Views — Standard-Mapping (login, meine, admin_maschinen, admin_benutzer)

Diese vier Views enthalten **nur** Klassen aus der Standard-Mapping-Tabelle (keine blauen Sonderflächen).

**Files:**
- Modify: `frontend/js/views/login.js`
- Modify: `frontend/js/views/meine.js`
- Modify: `frontend/js/views/admin_maschinen.js`
- Modify: `frontend/js/views/admin_benutzer.js`

- [ ] **Step 1: Standard-Mapping auf alle vier Dateien anwenden**

Für jede der vier Dateien jede hartkodierte Hell-Klasse gemäß **Standard-Klassen-Mapping** (oben) ersetzen. Reihenfolge beachten: längere/spezifischere zuerst, damit keine Teil-Treffer entstehen. Empfohlenes Kommando pro Datei (Beispiel `login.js`):

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app/frontend/js
sed -i \
  -e 's/hover:bg-slate-50/hover:bg-surface-2/g' \
  -e 's/hover:bg-slate-100/hover:bg-surface-2/g' \
  -e 's/bg-slate-50/bg-bg/g' \
  -e 's/bg-slate-100/bg-surface-2/g' \
  -e 's/bg-white/bg-surface/g' \
  -e 's/text-slate-900/text-txt/g' \
  -e 's/text-slate-800/text-txt/g' \
  -e 's/text-slate-700/text-txt-2/g' \
  -e 's/text-slate-600/text-muted/g' \
  -e 's/text-slate-500/text-muted/g' \
  -e 's/text-slate-400/text-muted-2/g' \
  -e 's/border-slate-200/border-border/g' \
  -e 's/border-slate-300/border-border/g' \
  views/login.js views/meine.js views/admin_maschinen.js views/admin_benutzer.js
```

- [ ] **Step 2: Kontrolle, dass keine Hell-Klassen übrig sind**

```bash
grep -nE "(bg|text|border|hover:bg)-(white|slate)-?[0-9]*|bg-white|text-white" views/login.js views/meine.js views/admin_maschinen.js views/admin_benutzer.js
```
Erwartet: **keine Ausgabe** (außer evtl. `text-white` auf farbigen Buttons — in diesen vier Dateien laut Inventar nicht vorhanden, also wirklich leer).

- [ ] **Step 3: Eingabefelder prüfen (Login/Benutzer/Maschinen-Suche)**

Eingabefelder, die vorher `bg-white border-slate-300` waren, sind nun `bg-surface border-border`. Falls ein `<input>` keine explizite `bg-*` hatte, ergänze `bg-surface text-txt` direkt an der Input-Klassenliste, damit das Feld nicht hell-default bleibt. Suchen:
```bash
grep -nE "<input|class=\"[^\"]*border-border" views/login.js views/admin_benutzer.js views/admin_maschinen.js
```
Für jedes gefundene Eingabefeld sicherstellen, dass die Klassen `bg-surface text-txt placeholder:text-muted-2` enthalten; fehlt etwas, ergänzen.

- [ ] **Step 4: Regression + manueller Check**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser: Login-Seite, „Meine“, Admin→Maschinenliste, Admin→Benutzer durchsehen — alle Flächen dunkel, Text lesbar, Eingabefelder dunkel.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/login.js frontend/js/views/meine.js frontend/js/views/admin_maschinen.js frontend/js/views/admin_benutzer.js
git commit -m "Design: einfache Views auf Dark+Lime (login/meine/maschinen/benutzer)"
```

---

## Task 5: Admin-Dashboard — Mapping + Status-Kachelfarben (`admin_dashboard.js`)

**Files:**
- Modify: `frontend/js/views/admin_dashboard.js`

- [ ] **Step 1: Standard-Mapping anwenden**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app/frontend/js
sed -i \
  -e 's/hover:bg-slate-50/hover:bg-surface-2/g' \
  -e 's/bg-slate-50/bg-bg/g' \
  -e 's/bg-white/bg-surface/g' \
  -e 's/text-slate-900/text-txt/g' \
  -e 's/text-slate-800/text-txt/g' \
  -e 's/text-slate-700/text-txt-2/g' \
  -e 's/text-slate-600/text-muted/g' \
  -e 's/text-slate-500/text-muted/g' \
  -e 's/text-slate-400/text-muted-2/g' \
  -e 's/border-slate-200/border-border/g' \
  -e 's/border-slate-300/border-border/g' \
  views/admin_dashboard.js
```

- [ ] **Step 2: Statistik-Kacheln in Status-Farben**

Öffne `views/admin_dashboard.js` und prüfe die Statistik-Zahlen. Sind die Kennzahlen für Verfügbar/Ausgeliehen/Defekt/Wartung als Zahl gerendert, soll die jeweilige Zahl die Status-Farbe tragen:
- Verfügbar → `text-ok`
- Ausgeliehen → `text-lent`
- Defekt → `text-broken`
- Wartung → `text-maint`

Konkret: an der jeweiligen Zahl-Span die Farbklasse ergänzen (Beispiel-Muster):
```js
`<div class="text-2xl font-extrabold text-ok">${stats.verfuegbar}</div>`
```
Analog für `lent` (ausgeliehen), `broken` (defekt), `maint` (wartung). Gibt es keine getrennten Kennzahlen, diesen Step überspringen (Mapping aus Step 1 genügt).

- [ ] **Step 3: Kontrolle Resthelligkeit**

```bash
grep -nE "(bg|text|border|hover:bg)-(white|slate)-?[0-9]*|bg-white" views/admin_dashboard.js
```
Erwartet: keine Ausgabe.

- [ ] **Step 4: Regression + manueller Check**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser: Admin-Dashboard — Kacheln dunkel, Kennzahlen in den vier Status-Farben.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/admin_dashboard.js
git commit -m "Design: Admin-Dashboard Dark+Lime + Status-Kachelfarben"
```

---

## Task 6: Admin-Historie — Mapping + blaues Badge (`admin_historie.js`)

**Files:**
- Modify: `frontend/js/views/admin_historie.js`

- [ ] **Step 1: Standard-Mapping anwenden**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app/frontend/js
sed -i \
  -e 's/bg-white/bg-surface/g' \
  -e 's/text-slate-900/text-txt/g' \
  -e 's/text-slate-700/text-txt-2/g' \
  -e 's/text-slate-600/text-muted/g' \
  -e 's/text-slate-500/text-muted/g' \
  -e 's/border-slate-200/border-border/g' \
  views/admin_historie.js
```

- [ ] **Step 2: Blaues Badge `bg-blue-100 text-blue-800` umstellen**

Finde die Stelle:
```bash
grep -n "bg-blue-100\|text-blue-800" views/admin_historie.js
```
Ersetze die Klassenkombination `bg-blue-100 text-blue-800` (ein „Ausgeliehen/extern“-Hinweis-Chip) durch den dunklen Chip-Stil:
```
bg-surface-2 text-lent
```
(also `bg-blue-100` → `bg-surface-2` und `text-blue-800` → `text-lent`).

- [ ] **Step 3: Kontrolle Resthelligkeit**

```bash
grep -nE "(bg|text|border)-(white|slate|blue)-?[0-9]*|bg-white" views/admin_historie.js
```
Erwartet: keine Ausgabe.

- [ ] **Step 4: Regression + manueller Check**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser: Admin → eine Maschine → Historie — Liste dunkel, Empfänger-/Status-Hinweise lesbar.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/admin_historie.js
git commit -m "Design: Admin-Historie Dark+Lime (inkl. Badge)"
```

---

## Task 7: Maschinen-Detail & Maschinen-Formular — Mapping + blaue Auswahl-/Info-Flächen

Beide Views nutzen Blau als Auswahl-/Info-/Primär-Akzent. Standard-Mapping zuerst, dann die blauen Sonderfälle.

**Files:**
- Modify: `frontend/js/views/maschine.js`
- Modify: `frontend/js/views/admin_maschine_form.js`

- [ ] **Step 1: Standard-Mapping auf beide Dateien anwenden**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app/frontend/js
sed -i \
  -e 's/hover:bg-slate-50/hover:bg-surface-2/g' \
  -e 's/bg-slate-100/bg-surface-2/g' \
  -e 's/bg-slate-50/bg-bg/g' \
  -e 's/bg-white/bg-surface/g' \
  -e 's/text-slate-900/text-txt/g' \
  -e 's/text-slate-800/text-txt/g' \
  -e 's/text-slate-700/text-txt-2/g' \
  -e 's/text-slate-600/text-muted/g' \
  -e 's/text-slate-500/text-muted/g' \
  -e 's/border-slate-200/border-border/g' \
  -e 's/border-slate-300/border-border/g' \
  views/maschine.js views/admin_maschine_form.js
```

- [ ] **Step 2: Blaue Flächen in `maschine.js` umstellen**

Finde sie:
```bash
grep -nE "blue-(50|200|700|800|900)" views/maschine.js
```
Dies ist eine Info-/Hinweisbox (z.B. „ausgeliehen an …“). Ersetze:
- `bg-blue-50` → `bg-surface-2`
- `border-blue-200` → `border-border`
- `text-blue-900` → `text-txt`
- `text-blue-800` → `text-txt-2`
- `text-blue-700` → `text-lent`

- [ ] **Step 3: Blaue Flächen in `admin_maschine_form.js` umstellen**

Finde sie:
```bash
grep -nE "blue-(50|500|600|700)|text-white" views/admin_maschine_form.js
```
Hier sind eine **Auswahl-/Aktiv-Markierung** (Foto/Anleitung-Upload) und ein **Primär-Button**. Ersetze:
- Auswahl-/Aktiv-Fläche: `bg-blue-50` → `bg-surface-2`, `border-blue-500` → `border-accent`, `text-blue-600` → `text-accent`
- Primär-Button `bg-blue-600 hover:bg-blue-700 text-white`: ersetze diese drei Klassen durch `bg-accent hover:brightness-95 text-accent-ink`. (Falls bequemer: den Button-`class`-String durch `${btnClasses('primary')}` ersetzen und `btnClasses` importieren.)
- Übrige `text-white` (auf der ehemals blauen Fläche): → `text-accent-ink`.

- [ ] **Step 4: Eingabefelder im Formular dunkel**

Formularfelder waren `bg-white border-slate-300` → jetzt `bg-surface border-border`. Ergänze für gute Lesbarkeit an jedem `<input>`/`<textarea>`/`<select>` die Klassen `text-txt placeholder:text-muted-2`, falls nicht vorhanden:
```bash
grep -nE "<input|<textarea|<select" views/admin_maschine_form.js
```

- [ ] **Step 5: Kontrolle Resthelligkeit (beide Dateien)**

```bash
grep -nE "(bg|text|border|hover:bg)-(white|slate|blue)-?[0-9]*|bg-white" views/maschine.js views/admin_maschine_form.js
```
Erwartet: keine Ausgabe.

- [ ] **Step 6: Regression + manueller Check (wichtigste Screens)**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`. Browser:
- Mitarbeiter: Maschine per Code öffnen → Detail dunkel, Foto/Zubehör, Ausleih-Dialog, Rückgabe-Dialog.
- Admin: Maschine „bearbeiten“ + „neu“ → Formularfelder dunkel, Upload-Auswahl mit Lime-Rahmen, Primär-Button Lime.

- [ ] **Step 7: Commit**

```bash
git add frontend/js/views/maschine.js frontend/js/views/admin_maschine_form.js
git commit -m "Design: Maschinen-Detail & -Formular Dark+Lime (inkl. Auswahl/Button)"
```

---

## Task 8: Gesamt-Verifikation & Abschluss

**Files:** keine Änderung.

- [ ] **Step 1: Gesamte Suite grün**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest -q
```
Erwartet: `32 passed`.

- [ ] **Step 2: Projektweiter Helligkeits-Scan (nichts übersehen)**

```bash
grep -rnE "(bg|text|border|hover:bg)-(white|slate|blue|gray|zinc|neutral)-?[0-9]*|bg-white" frontend/js frontend/index.html
```
Erwartet: nur bewusst belassene Treffer (z.B. `text-rose-600` im Fehler-Catch von `app.js`, sowie Backdrop `bg-black/50` ist ohnehin nicht im Muster). Jede unerwartete Hell-Klasse beheben und committen.

- [ ] **Step 3: Vollständiger Klick-Durchlauf**

Login → Mitarbeiter-Flow (Meine, Code öffnen, Ausleihen, Zurückgeben) → Admin-Flow (Dashboard, Maschinen, anlegen/bearbeiten, Historie, Benutzer). Prüfen: durchgehend dunkel, lesbar, Status-Farben korrekt, Lime nur für Marke/Aktion.

- [ ] **Step 4: Branch zusammenführen**

Mit dem `superpowers:finishing-a-development-branch`-Skill abschließen (Merge nach `main` / PR / Cleanup, je nach Wunsch).

---

## Self-Review-Notiz (Plan ↔ Spec)

- Spec „Design-Tokens“ → Task 1 (Tailwind-Config mit allen 14 Tokens). ✓
- Spec „index.html“ (Config, theme-color, body) → Task 1. ✓
- Spec „ui.js“ (alle 7 Bausteine + logoMarkup) → Task 2. ✓
- Spec „app.js“ (Topbar/Bottom-Nav/404 + Logo) → Task 3. ✓
- Spec „Logo (Platzhalter)“ → Task 2 Step 2 (`logoMarkup`). ✓
- Spec „Views nachziehen“ (8 Views) → Tasks 4–7 (alle 8 abgedeckt). ✓
- Spec „Kontrast/Zugänglichkeit“ → dunkler Ink auf Lime in Task 2; Status-Farben hell. ✓
- Spec „Tests/Verifikation“ (pytest grün + manuell) → in jeder Task + Task 8. ✓
- Spec „YAGNI“ (keine Funktions-/Nav-/Layout-Änderung, kein Icon-Set/Font/Build) → eingehalten; Nav-Aktiv-Status bewusst ausgelassen (Task 3 Step 3 Hinweis). ✓
