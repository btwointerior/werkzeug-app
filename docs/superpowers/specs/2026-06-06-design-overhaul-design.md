# Design-Overhaul — „Signal“ (Dark + Lime) — Design

**Status:** Freigegeben (2026-06-06)

## Ziel

Die App bekommt einen professionellen, markentauglichen Auftritt statt des
generischen Standard-Tailwind-Looks. Es ist ein **rein optisches** Overhaul:
Bildschirme, Navigation und Abläufe bleiben unverändert, ebenso die gesamte
Backend-Funktionalität.

Quelle: To-Do „DESIGN: Das komplette Design mit Claude-Front-Design überarbeiten“.

## Entscheidungen (aus dem Brainstorming)

| Frage | Entscheidung |
|-------|--------------|
| Hauptziel | Professioneller / markentauglicher Look |
| Branding | Logo vorhanden, Farben frei → eigene Palette entwickelt |
| Logo | **Platzhalter** „B2“-Monogramm, wird später 1:1 ausgetauscht |
| Umfang | **Nur Optik** — keine Layout-/Navigations-/Ablauf-Änderungen |
| Stilrichtung | „Signal“: dunkler Grund + **Lime** als Signal-/Markenfarbe |
| Signalfarbe | Lime `#d4f000` |

## Design-Tokens

Zentrale Werte, aus denen sich alles ableitet:

| Token | Wert | Verwendung |
|-------|------|------------|
| `bg` (Grund) | `#0b0f1a` | Seitenhintergrund, Header, Bottom-Nav |
| `surface` (Karte) | `#151b2b` | Karten, Modals, Eingabefelder |
| `surface-2` | `#1e2740` | sekundäre Flächen / gefüllte Sekundär-Buttons |
| `border` | `#1e2740` | Rahmen, Trennlinien |
| `text` | `#ffffff` | Überschriften, primärer Text |
| `text-2` | `#cbd5e1` | Fließtext |
| `muted` | `#94a3b8` | Sekundärtext |
| `muted-2` | `#64748b` | Labels, Platzhalter |
| **`accent`** (Lime) | `#d4f000` | Marke, primäre Buttons, aktives Nav, Logo |
| `accent-ink` | `#0b0f1a` | Text **auf** Lime (Buttons) |
| Status verfügbar | `#34d399` (grün) | Badge, Statistik |
| Status ausgeliehen | `#60a5fa` (blau) | Badge, Statistik |
| Status defekt | `#f87171` (rot) | Badge, Statistik |
| Status wartung | `#fbbf24` (gelb) | Badge, Statistik |

**Grundsatz:** Lime ist ausschließlich Marke + Aktion. Die vier Status-Zustände
haben eigene, davon klar unterscheidbare Farben — Lime ist **kein** Status.

**Weitere Tokens:**
- Rundungen: Karten/Modals `rounded-2xl`, Buttons/Inputs `rounded-xl`, Badges `rounded-full`.
- Schatten: dezent (`shadow-lg` nur auf Modals/Toasts, Karten flach mit Border).
- Touch-Ziele: min. 48px (bleibt wie bisher).
- Schrift: weiterhin System-Font; Überschriften kräftiger (`font-bold`/`font-semibold`).
- Status-Badges erhalten dunklen Chip-Hintergrund (`surface-2`) + farbigen Text/Punkt.

## Architektur

Die Optik wird **zentralisiert** statt in jeder Datei einzeln gepflegt. Kein neues
Build-Tool, kein Framework — der triviale Setup-Charakter (Tailwind via CDN,
Vanilla-JS) bleibt erhalten.

1. **Tailwind-Theme** in `index.html` über `tailwind.config` definieren: die
   Tokens oben als benannte Farben (`bg`, `surface`, `surface-2`, `border`,
   `accent`, `accent-ink`, `txt`, `txt-2`, `muted`, `muted-2`, `ok`, `lent`,
   `broken`, `maint`). So heißt es künftig `bg-surface` statt `bg-[#151b2b]` —
   lesbar und an **einer** Stelle änderbar (wichtig fürs spätere echte Logo/CI).
2. **Dunkler Grund global** am `body` setzen + `theme-color`-Meta auf `#0b0f1a`.
3. **Geteilte Bausteine zuerst** (`ui.js`) — sie sind bereits zentral, ein Update
   zieht durch fast die ganze App.
4. **Chrome** (`app.js`): Topbar + Bottom-Nav + Platzhalter-Logo.
5. **Views einzeln nachziehen** (8 Dateien): verbliebene hartkodierte
   Hell-Klassen auf die Tokens umstellen, jede Seite im Browser gegengeprüft.

Schritte 1–3 erzeugen den Großteil der Wirkung an wenigen Stellen; Schritt 5 ist
dann risikoarmes Durchgehen.

## `frontend/index.html`

- `<script src="https://cdn.tailwindcss.com">` behalten; **direkt danach** ein
  `tailwind.config = { theme: { extend: { colors: { … Tokens … } } } }`-Block.
- `<meta name="theme-color">` von `#2563eb` auf `#0b0f1a`.
- `<body>`-Klassen von `bg-slate-50 text-slate-900` auf `bg-bg text-txt-2`.
- Toast-Container / Modal-Root bleiben strukturell unverändert.

## `frontend/js/ui.js` (geteilte Bausteine)

- `btnClasses`: Varianten neu einfärben —
  `primary` = `bg-accent text-accent-ink` (Lime),
  `secondary` = `bg-surface-2 text-txt-2`,
  `success/warning/danger` = Status-Grün/Gelb/Rot mit dunklem Ink,
  `ghost` = transparent + `hover:bg-surface-2`. Rundung `rounded-xl`.
- `modal`: Card `bg-surface` + `border border-border`, Header/Footer-Trenner
  `border-border`, Text hell. Backdrop bleibt `bg-black/50`.
- `statusBadge`: Chip-Hintergrund `bg-surface-2`, Text in der jeweiligen
  Status-Farbe, vorangestellter farbiger Punkt (`●`).
- `toast`: Erfolg/Fehler/Info auf Status-Grün/Rot bzw. `surface-2`.
- `spinner`: Ring in `accent`.
- `leerZustand`: Text in `muted`.
- `confirmDialog`: erbt automatisch (nutzt `modal` + `btnClasses`).

## `frontend/js/app.js` (Chrome)

- **Topbar**: `bg-bg border-b border-border`; links das **Platzhalter-Logo**
  (Lime-Quadrat `rounded-lg` mit `B2`-Monogramm in `accent-ink`) + Titel in
  `text-txt`; „Abmelden“ als Ghost-Button.
- **Bottom-Nav**: `bg-bg border-t border-border`; Icons/Labels in `muted`,
  **aktiver** Eintrag in `accent`. Emoji-Icons bleiben vorerst (kein Icon-Set
  im Scope).
- Fehler-/404-Ansichten in diesem File ebenfalls auf dunkle Tokens.

## Logo (Platzhalter)

Ein schlichtes „B2“-Monogramm als Inline-Markup (Lime-Quadrat, dunkler Text),
gekapselt als kleine Helfer-Funktion `logoMarkup()` in `ui.js`, damit der spätere
Austausch gegen das echte B2-Interior-Logo an **einer** Stelle passiert.

## Views nachziehen (je Datei kurz im Browser prüfen)

Hartkodierte Hell-Utilities (`bg-white`, `bg-slate-50`, `text-slate-900`,
`border-slate-200`, `text-slate-*` …) → Tokens (`bg-surface`, `bg-bg`,
`text-txt`, `border-border`, `text-muted` …). Status-/Aktionsfarben über die
geteilten Bausteine. Betroffen:

- `views/login.js`
- `views/meine.js`
- `views/maschine.js` (inkl. Ausleih-/Rückgabe-Dialoge, Foto, Zubehör)
- `views/admin_dashboard.js` (Statistik-Kacheln in Status-Farben)
- `views/admin_maschinen.js`
- `views/admin_maschine_form.js` (Formularfelder: `bg-surface` + `border-border`)
- `views/admin_historie.js`
- `views/admin_benutzer.js`

## Kontrast / Zugänglichkeit

- Fließtext `text-2` (`#cbd5e1`) auf `bg`/`surface`: gut lesbar (Kontrast > 7:1).
- Lime-Buttons tragen **dunklen** Text (`accent-ink`), nie weißen.
- Status-Farben ausreichend hell für dunklen Grund (heller 400er-Bereich).

## Tests / Verifikation

- **Keine** funktionalen Änderungen → die bestehende pytest-Suite (32 Tests)
  muss unverändert grün bleiben (Regressionsschutz):
  `~/.venvs/werkzeug/bin/python -m pytest -q`.
- Optik wird **manuell im Browser** verifiziert (Vanilla-JS ohne UI-Test-Harness),
  Screen für Screen gemäß der Liste oben, jeweils mit den vorhandenen Demo-Daten
  (4 Maschinen, 7 Zubehör, 3 Benutzer). Prüfpunkte je Screen: Lesbarkeit,
  korrekte Status-Farben, Touch-Ziele, keine versehentlich hellen Restflächen.
- Login-, Mitarbeiter- und Admin-Flow je einmal komplett durchklicken.

## Bewusst nicht im Scope (YAGNI)

- Keine Änderung an Screens, Navigation, Routen oder Abläufen.
- Keine Backend-/API-/Datenmodell-Änderungen.
- Kein Light-/Dark-Umschalter — die App ist durchgängig dunkel.
- Kein professionelles Icon-Set — Emoji-Icons bleiben vorerst.
- Kein finales Logo — Platzhalter, späterer Austausch an einer Stelle.
- Keine neuen Schriftarten / Web-Fonts (System-Font bleibt).
- Kein Build-Step / keine zusätzlichen Abhängigkeiten.
