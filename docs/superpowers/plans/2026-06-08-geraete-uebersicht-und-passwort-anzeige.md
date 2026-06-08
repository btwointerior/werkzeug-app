# Geräte-Übersicht + Klartext-Passwort-Anzeige — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine durchsuch- und filterbare Geräte-Übersicht für alle eingeloggten Nutzer, plus eine Klartext-Passwort-Anzeige für Admins.

**Architecture:** Neuer Nutzer-Endpunkt `GET /api/maschinen` liefert die komplette Maschinenliste; Suche/Status-Filter laufen client-seitig über ein gemeinsames, rein getestetes Modul (`filter.js`), das sowohl die neue Geräte-View als auch die Admin-Maschinenliste nutzt. Für die Passwort-Anzeige wird zusätzlich zum Hash ein Klartextfeld gespeichert und über `BenutzerOut` nur an Admin-Endpunkte ausgeliefert.

**Tech Stack:** FastAPI + SQLAlchemy (Backend), Vanilla-JS-ES-Module + Tailwind (Frontend), pytest + `node:test` (Tests).

**Umgebung:** Python-Tests im venv: `source ~/.venvs/werkzeug/bin/activate` vorab ausführen. JS-Tests: `node --test '<datei>'`. Alle Pfade relativ zu `/media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app`.

---

## Task 1: Backend-Endpunkt `GET /api/maschinen` (Geräte-Liste für alle Nutzer)

**Files:**
- Modify: `backend/routers/maschinen_router.py` (neuer Endpunkt am Dateiende, vor evtl. weiteren Routen)
- Test: `tests/test_geraete_liste.py`

- [ ] **Step 1: Test schreiben**

Create `tests/test_geraete_liste.py`:

```python
"""Tests für die Geräte-Übersicht (GET /api/maschinen) für eingeloggte Nutzer."""

from backend.models import Maschine, MaschinenStatus
from .conftest import auth_header, make_user


def _maschine(db, code, name, status=MaschinenStatus.VERFUEGBAR):
    m = Maschine(maschinen_code=code, name=name, status=status)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_mitarbeiter_sieht_alle_maschinen(db, client):
    user = make_user(db, "max")
    _maschine(db, "M-0001", "Bohrmaschine", MaschinenStatus.VERFUEGBAR)
    _maschine(db, "M-0002", "Kreissäge", MaschinenStatus.DEFEKT)

    r = client.get("/api/maschinen", headers=auth_header(user))

    assert r.status_code == 200
    codes = [m["maschinen_code"] for m in r.json()]
    assert codes == ["M-0001", "M-0002"]  # sortiert nach Code, inkl. defekt


def test_geraete_liste_ohne_login_401(db, client):
    r = client.get("/api/maschinen")
    assert r.status_code == 401
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `source ~/.venvs/werkzeug/bin/activate && pytest tests/test_geraete_liste.py -v`
Expected: FAIL — `test_mitarbeiter_sieht_alle_maschinen` liefert 404 (Route existiert noch nicht).

- [ ] **Step 3: Endpunkt implementieren**

In `backend/routers/maschinen_router.py` ans Dateiende anhängen (nutzt bereits importierte `get_current_user`, `Maschine`, `MaschineOut`, `maschine_zu_out`):

```python
@router.get("", response_model=list[MaschineOut])
def alle_maschinen(
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MaschineOut]:
    """Geräte-Übersicht: komplette Maschinenliste für eingeloggte Nutzer.
    Suche/Status-Filter laufen client-seitig, daher hier keine Query-Parameter."""
    maschinen = db.query(Maschine).order_by(Maschine.maschinen_code).all()
    return [maschine_zu_out(m, current_user.id) for m in maschinen]
```

- [ ] **Step 4: Test laufen lassen, Erfolg prüfen**

Run: `source ~/.venvs/werkzeug/bin/activate && pytest tests/test_geraete_liste.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/maschinen_router.py tests/test_geraete_liste.py
git commit -m "feat(backend): GET /api/maschinen – Geräte-Liste für alle Nutzer"
```

---

## Task 2: Gemeinsames Filter-Modul `filter.js`

**Files:**
- Create: `frontend/js/filter.js`
- Test: `tests/js/filter.test.mjs`

- [ ] **Step 1: Test schreiben**

Create `tests/js/filter.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filterMaschinen } from '../../frontend/js/filter.js';

const LISTE = [
  { name: 'Bohrmaschine',  maschinen_code: 'M-0001', hersteller: 'Bosch',  platznummer: 'A1', seriennummer: 'SN-111', status: 'verfuegbar' },
  { name: 'Kreissäge',     maschinen_code: 'M-0002', hersteller: 'Makita', platznummer: 'B2', seriennummer: 'SN-222', status: 'ausgeliehen' },
  { name: 'Akkuschrauber', maschinen_code: 'M-0003', hersteller: 'Bosch',  platznummer: 'A2', seriennummer: 'SN-333', status: 'defekt' },
];
const codes = (r) => r.map((m) => m.maschinen_code);

test('leere Eingabe = ungefilterte Liste', () => {
  assert.equal(filterMaschinen(LISTE, {}).length, 3);
  assert.equal(filterMaschinen(LISTE, { suche: '', status: '' }).length, 3);
});

test('Freitext findet über Name', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'säge' })), ['M-0002']);
});

test('Freitext findet über Code', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'm-0003' })), ['M-0003']);
});

test('Freitext findet über Hersteller (mehrere Treffer)', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'bosch' })), ['M-0001', 'M-0003']);
});

test('Freitext findet über Platznummer', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'b2' })), ['M-0002']);
});

test('Freitext findet über Seriennummer', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'sn-222' })), ['M-0002']);
});

test('case-insensitiv und getrimmt', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: '  BOHR ' })), ['M-0001']);
});

test('Status-Filter exakt', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { status: 'defekt' })), ['M-0003']);
});

test('Suche + Status kombiniert', () => {
  assert.deepEqual(codes(filterMaschinen(LISTE, { suche: 'bosch', status: 'defekt' })), ['M-0003']);
});

test('kein Treffer = leeres Array', () => {
  assert.deepEqual(filterMaschinen(LISTE, { suche: 'xyz' }), []);
});

test('Nicht-Array = leeres Array', () => {
  assert.deepEqual(filterMaschinen(null, {}), []);
});
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `node --test 'tests/js/filter.test.mjs'`
Expected: FAIL — Modul `frontend/js/filter.js` existiert nicht (ERR_MODULE_NOT_FOUND).

- [ ] **Step 3: Modul implementieren**

Create `frontend/js/filter.js`:

```js
// Gemeinsame, reine Filterfunktion für Maschinenlisten.
// Genutzt von der Geräte-Übersicht (views/geraete.js) und der
// Admin-Maschinenliste (views/admin_maschinen.js). Ohne DOM-Abhängigkeit,
// damit sie mit node:test unit-getestet werden kann.

// Felder, die die Freitext-Suche durchsucht.
const SUCH_FELDER = ['name', 'maschinen_code', 'hersteller', 'platznummer', 'seriennummer'];

// Filtert eine Maschinenliste nach Freitext (suche) und Status.
// - suche:  durchsucht SUCH_FELDER, case-insensitiv & getrimmt; leer = kein Filter
// - status: exakter Vergleich gegen m.status; leer/falsy = alle Status
export function filterMaschinen(liste, { suche = '', status = '' } = {}) {
  if (!Array.isArray(liste)) return [];
  const q = String(suche).trim().toLowerCase();
  return liste.filter((m) => {
    if (status && m.status !== status) return false;
    if (!q) return true;
    return SUCH_FELDER.some((feld) => {
      const wert = m[feld];
      return typeof wert === 'string' && wert.toLowerCase().includes(q);
    });
  });
}
```

- [ ] **Step 4: Test laufen lassen, Erfolg prüfen**

Run: `node --test 'tests/js/filter.test.mjs'`
Expected: PASS (`# pass 11`, `# fail 0`).

- [ ] **Step 5: Commit**

```bash
git add frontend/js/filter.js tests/js/filter.test.mjs
git commit -m "feat(frontend): gemeinsames filterMaschinen-Modul + Tests"
```

---

## Task 3: Geräte-View + Route + Bottom-Nav-Eintrag

**Files:**
- Create: `frontend/js/views/geraete.js`
- Modify: `frontend/js/app.js` (Import Zeile ~9; ROUTEN ~Zeile 30; Nav-`links` ~Zeile 104)

- [ ] **Step 1: View erstellen**

Create `frontend/js/views/geraete.js`:

```js
import { api } from '../api.js';
import {
  escapeHtml, leerZustand, spinner, statusBadge,
} from '../ui.js';
import { filterMaschinen } from '../filter.js';

export async function renderGeraete() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <main class="max-w-3xl mx-auto pb-24 pt-4 px-4">
      <h1 class="text-2xl font-bold text-txt mb-4">Geräte</h1>
      <div class="flex gap-2 mb-4">
        <input id="g-suche" placeholder="Suche..."
               class="flex-1 border border-border rounded-lg px-3 py-2 bg-surface text-txt placeholder:text-muted">
        <select id="g-status" class="border border-border rounded-lg px-3 py-2 bg-surface text-txt">
          <option value="">Alle Status</option>
          <option value="verfuegbar">Verfügbar</option>
          <option value="ausgeliehen">Ausgeliehen</option>
          <option value="defekt">Defekt</option>
          <option value="wartung">In Wartung</option>
        </select>
      </div>
      <div id="g-liste">${spinner()}</div>
    </main>`;

  const suche = document.getElementById('g-suche');
  const stat  = document.getElementById('g-status');
  const liste = document.getElementById('g-liste');
  let alle = [];

  const render = () => {
    const treffer = filterMaschinen(alle, { suche: suche.value, status: stat.value });
    if (!treffer.length) {
      liste.innerHTML = leerZustand('Keine Geräte gefunden.');
      return;
    }
    liste.innerHTML = treffer.map((m) => `
      <a href="#/m/${encodeURIComponent(m.maschinen_code)}"
         class="block bg-surface rounded-lg shadow-sm p-4 mb-3 border border-border hover:bg-surface-2">
        <div class="flex justify-between items-start gap-3">
          <div class="min-w-0">
            <div class="font-semibold text-txt truncate">${escapeHtml(m.name)}</div>
            <div class="text-sm text-muted truncate">
              ${escapeHtml(m.maschinen_code)}${m.platznummer ? ` · ${escapeHtml(m.platznummer)}` : ''}
            </div>
          </div>
          ${statusBadge(m.status)}
        </div>
      </a>`).join('');
  };

  suche.oninput = render;
  stat.onchange = render;

  try {
    alle = await api.get('/api/maschinen');
    render();
  } catch (err) {
    liste.innerHTML =
      `<div class="p-4 text-rose-600">${escapeHtml(err.detail || 'Fehler beim Laden.')}</div>`;
  }
}
```

- [ ] **Step 2: Import in `app.js` ergänzen**

In `frontend/js/app.js` nach der Zeile `import { renderMeine } from './views/meine.js';` (Zeile 8) einfügen:

```js
import { renderGeraete } from './views/geraete.js';
```

- [ ] **Step 3: Route in `app.js` ergänzen**

In `frontend/js/app.js` im `ROUTEN`-Array direkt nach der Zeile
`{ pattern: /^#\/meine$/, view: renderMeine },` einfügen:

```js
  { pattern: /^#\/geraete$/, view: renderGeraete },
```

- [ ] **Step 4: Bottom-Nav-Eintrag in `app.js` ergänzen**

In `frontend/js/app.js` das `links`-Array (beginnt mit `{ hash: '#/meine', label: 'Meine', icon: '📋' },`) so erweitern, dass „Geräte" an erster Stelle steht:

```js
  const links = [
    { hash: '#/geraete', label: 'Geräte', icon: '🔧' },
    { hash: '#/meine',   label: 'Meine',  icon: '📋' },
    { label: 'Code',     icon: '🔍', action: scanOrAsk },
  ];
```

- [ ] **Step 5: Manuell verifizieren**

Server läuft via `uvicorn backend.main:app --reload` (Port 8000). Im Browser http://127.0.0.1:8000 einloggen (auch als Nicht-Admin), unten „Geräte" antippen.
Expected: Liste aller Maschinen; Tippen im Suchfeld filtert live; Status-Dropdown filtert; Klick auf Karte öffnet `#/m/CODE`.

- [ ] **Step 6: Commit**

```bash
git add frontend/js/views/geraete.js frontend/js/app.js
git commit -m "feat(frontend): Geräte-Übersicht mit Suche/Filter + Nav-Eintrag"
```

---

## Task 4: Admin-Maschinenliste auf gemeinsames Filter-Modul umstellen (client-seitig)

**Kontext:** `admin_maschinen.js` filtert heute server-seitig (`/api/admin/maschinen?suche=&status=`). Umstellung auf: einmal komplette Liste laden, dann client-seitig mit `filterMaschinen` filtern. Dadurch durchsucht die Admin-Suche zusätzlich Hersteller & Platznummer, und die Filterlogik ist mit der Geräte-View geteilt (DRY). Bulk-Auswahl, QR-Druck und Löschen bleiben unverändert.

**Files:**
- Modify: `frontend/js/views/admin_maschinen.js` (Import oben; Block ab `let timer;` bis Dateiende)

- [ ] **Step 1: Import ergänzen**

In `frontend/js/views/admin_maschinen.js` nach dem bestehenden `ui.js`-Import-Block einfügen:

```js
import { filterMaschinen } from '../filter.js';
```

- [ ] **Step 2: Filter-/Lade-Block ersetzen**

In `frontend/js/views/admin_maschinen.js` den gesamten Block — beginnend bei `  let timer;` und der Zeile `  const lade = async () => {` bis zum Funktionsende (die drei Abschlusszeilen `suche.oninput = ...`, `stat.onchange = lade;`, `lade();` und die schließende `}`) — durch Folgendes ersetzen:

```js
  let alle = [];

  const zeige = () => {
    const maschinen = filterMaschinen(alle, { suche: suche.value, status: stat.value });
    if (!maschinen.length) {
      liste.innerHTML = '<div class="text-center py-12 text-muted">Keine Treffer.</div>';
      return;
    }
    liste.innerHTML = maschinen.map((m) => `
      <div class="bg-surface border border-border rounded-lg p-3 mb-2">
        <div class="flex items-start gap-3">
          <label class="flex items-center pt-1 cursor-pointer">
            <input type="checkbox" data-sel="${m.id}" ${auswahl.has(m.id) ? 'checked' : ''}
                   class="w-5 h-5 accent-accent">
          </label>
          <a href="#/m/${encodeURIComponent(m.maschinen_code)}" class="flex-1 min-w-0">
            <div class="font-semibold text-txt truncate">${escapeHtml(m.name)}</div>
            <div class="text-sm text-muted truncate">
              ${escapeHtml(m.maschinen_code)}${m.platznummer ? ` · ${escapeHtml(m.platznummer)}` : ''}
            </div>
          </a>
          <div class="flex-shrink-0">${statusBadge(m.status)}</div>
        </div>
        <div class="flex gap-2 mt-3 flex-wrap">
          <a href="#/admin/maschinen/${m.id}/edit" class="${btnClasses('secondary')} text-sm">Bearbeiten</a>
          <a href="#/admin/maschinen/${m.id}/historie" class="${btnClasses('secondary')} text-sm">Historie</a>
          <button data-qr="${m.id}" class="${btnClasses('secondary')} text-sm">QR-Code</button>
          <button data-del="${m.id}" data-name="${escapeHtml(m.name)}"
                  class="${btnClasses('danger')} text-sm ml-auto">Löschen</button>
        </div>
      </div>`).join('');

    liste.querySelectorAll('input[data-sel]').forEach((c) => {
      c.onchange = () => {
        const id = +c.dataset.sel;
        if (c.checked) auswahl.add(id);
        else auswahl.delete(id);
        aktualisiereBar();
      };
    });

    liste.querySelectorAll('[data-qr]').forEach((b) => {
      b.onclick = async () => {
        try {
          await oeffneBlobImNeuenTab(`/api/admin/maschinen/${b.dataset.qr}/qr-code`);
        } catch (err) {
          toast(err.detail || 'QR-Code-Fehler.', 'error');
        }
      };
    });

    liste.querySelectorAll('[data-del]').forEach((b) => {
      b.onclick = async () => {
        const ok = await confirmDialog(
          `Maschine "${b.dataset.name}" wirklich löschen?`,
          { dangerous: true, okLabel: 'Löschen' },
        );
        if (!ok) return;
        try {
          await api.del(`/api/admin/maschinen/${b.dataset.del}`);
          toast('Maschine gelöscht.', 'success');
          auswahl.delete(+b.dataset.del);
          aktualisiereBar();
          ladeAlle();
        } catch (err) {
          toast(err.detail || 'Löschen fehlgeschlagen.', 'error');
        }
      };
    });
  };

  const ladeAlle = async () => {
    try {
      alle = await api.get('/api/admin/maschinen');
      zeige();
    } catch (err) {
      liste.innerHTML = `<div class="text-rose-600 p-4">${escapeHtml(err.detail)}</div>`;
    }
  };

  suche.oninput = zeige;
  stat.onchange = zeige;
  ladeAlle();
}
```

- [ ] **Step 3: JS-Syntax prüfen**

Run: `node --check frontend/js/views/admin_maschinen.js`
Expected: kein Output, Exit 0 (Datei ist syntaktisch gültig).

- [ ] **Step 4: Manuell verifizieren**

Im Browser als Admin → „Admin" → „Maschinen": Liste lädt; Suche filtert live (auch nach Hersteller/Platznummer); Status-Dropdown filtert; Mehrfachauswahl + „QR-Codes drucken" funktioniert; eine Maschine löschen aktualisiert die Liste.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/admin_maschinen.js
git commit -m "refactor(frontend): Admin-Maschinenliste nutzt gemeinsames filterMaschinen"
```

---

## Task 5: Backend — Klartext-Passwort speichern & ausliefern

**Sicherheitshinweis:** Auf ausdrücklichen, informierten Wunsch des Betreibers. Bestehende (gehashte) Passwörter werden NICHT sichtbar — nur ab jetzt neu gesetzte.

**Files:**
- Modify: `backend/models.py` (Spalte `passwort_klartext` ~Zeile 61; Methode `setze_passwort` ~Zeile 74)
- Modify: `backend/schemas.py` (`BenutzerOut` ~Zeile 185)
- Test: `tests/test_passwort_klartext.py`

- [ ] **Step 1: Test schreiben**

Create `tests/test_passwort_klartext.py`:

```python
"""Tests für die Klartext-Passwort-Speicherung & Admin-Anzeige."""

from backend.models import Rolle
from .conftest import auth_header, make_user


def test_setze_passwort_speichert_klartext(db):
    u = make_user(db, "max", passwort="geheim123")
    assert u.passwort_klartext == "geheim123"
    assert u.pruefe_passwort("geheim123") is True


def test_admin_benutzer_liefert_klartext(db, client):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    r = client.get("/api/admin/benutzer", headers=auth_header(admin))
    assert r.status_code == 200
    chef = next(b for b in r.json() if b["benutzername"] == "chef")
    assert chef["passwort_klartext"] == "adminpw"


def test_maschinen_endpunkt_leakt_kein_klartext(db, client):
    user = make_user(db, "max", passwort="geheim")
    r = client.get("/api/maschinen", headers=auth_header(user))
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `source ~/.venvs/werkzeug/bin/activate && pytest tests/test_passwort_klartext.py -v`
Expected: FAIL — `passwort_klartext` existiert weder am Modell noch im Schema (AttributeError / KeyError).

- [ ] **Step 3: Spalte am Modell ergänzen**

In `backend/models.py` in der Klasse `Benutzer` direkt nach der Zeile
`    passwort_hash = Column(String(255), nullable=False)` einfügen:

```python
    # ACHTUNG: Klartext-Passwort auf ausdrücklichen Wunsch des Betreibers, damit Admins es
    # ansehen können. Bewusst gegen die Sicherheitsempfehlung: bei einem DB-/Backup-Leak
    # liegen alle so gespeicherten Passwörter offen. Nur ab Einführung neu gesetzte Passwörter
    # sind befüllt (Alt-Hashes sind nicht rückrechenbar).
    passwort_klartext = Column(String(255), nullable=True)
```

- [ ] **Step 4: `setze_passwort` erweitern**

In `backend/models.py` die Methode `setze_passwort` ersetzen durch:

```python
    def setze_passwort(self, klartext: str) -> None:
        """Passwort als Hash speichern (für die Anmeldung maßgeblich) UND zusätzlich im
        Klartext (siehe passwort_klartext) für die Admin-Anzeige."""
        self.passwort_hash = pwd_context.hash(klartext)
        self.passwort_klartext = klartext
```

- [ ] **Step 5: `BenutzerOut`-Schema erweitern**

In `backend/schemas.py` in der Klasse `BenutzerOut` nach der Zeile `    aktiv: bool` einfügen:

```python
    passwort_klartext: Optional[str] = None
```

- [ ] **Step 6: Test laufen lassen, Erfolg prüfen**

Run: `source ~/.venvs/werkzeug/bin/activate && pytest tests/test_passwort_klartext.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Gesamte Test-Suite laufen lassen (Regression)**

Run: `source ~/.venvs/werkzeug/bin/activate && pytest -q`
Expected: alle Tests grün (keine Regression durch die Modell-/Schema-Änderung).

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/schemas.py tests/test_passwort_klartext.py
git commit -m "feat(backend): Klartext-Passwort speichern und an Admin ausliefern"
```

> **Deploy-Hinweis (nicht Teil dieses Commits):** `create_all` legt in bestehenden DBs keine neuen Spalten an. Nach dem Deploy auf Hetzner einmalig ausführen:
> `ALTER TABLE benutzer ADD COLUMN passwort_klartext VARCHAR(255);`

---

## Task 6: Frontend — Klartext-Passwort in der Benutzerverwaltung anzeigen

**Files:**
- Modify: `frontend/js/views/admin_benutzer.js` (Funktion `lade`: `liste.innerHTML`-Map + Event-Bindings)

- [ ] **Step 1: Passwort-Zeile in der Karte ergänzen**

In `frontend/js/views/admin_benutzer.js` innerhalb von `lade()` den `liste.innerHTML = benutzer.map(...)`-Ausdruck ersetzen durch:

```js
      liste.innerHTML = benutzer.map((b) => `
        <div class="bg-surface border border-border rounded-lg p-3 mb-2 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="font-medium text-txt truncate">${escapeHtml(b.voller_name)}</div>
            <div class="text-sm text-muted truncate">
              ${escapeHtml(b.benutzername)} · ${escapeHtml(b.rolle)}${b.aktiv ? '' : ' · <span class="text-rose-600 font-medium">gesperrt</span>'}
            </div>
            <div class="text-sm text-muted mt-1 flex items-center gap-2">
              <span>Passwort:</span>
              ${b.passwort_klartext
                ? `<span data-pw="${b.id}" class="font-mono">••••••••</span>
                   <button data-pwtoggle="${b.id}" data-shown="0"
                           class="text-accent text-xs underline">anzeigen</button>`
                : `<span class="italic">— (vor Umstellung gesetzt)</span>`}
            </div>
          </div>
          <button data-id="${b.id}" class="${btnClasses('secondary')} text-sm flex-shrink-0">Bearbeiten</button>
        </div>`).join('');
```

- [ ] **Step 2: Toggle-Bindings ergänzen**

In `frontend/js/views/admin_benutzer.js` direkt nach dem bestehenden Block
`liste.querySelectorAll('[data-id]').forEach((btn) => { ... });` einfügen:

```js
      liste.querySelectorAll('[data-pwtoggle]').forEach((btn) => {
        btn.onclick = () => {
          const id = +btn.dataset.pwtoggle;
          const span = liste.querySelector(`[data-pw="${id}"]`);
          const b = benutzer.find((x) => x.id === id);
          if (!span || !b) return;
          const shown = btn.dataset.shown === '1';
          span.textContent = shown ? '••••••••' : (b.passwort_klartext || '');
          btn.textContent = shown ? 'anzeigen' : 'verbergen';
          btn.dataset.shown = shown ? '0' : '1';
        };
      });
```

- [ ] **Step 3: JS-Syntax prüfen**

Run: `node --check frontend/js/views/admin_benutzer.js`
Expected: kein Output, Exit 0.

- [ ] **Step 4: Manuell verifizieren**

Im Browser als Admin → „Admin" → „Benutzer". Einen neuen Benutzer mit Passwort anlegen → in der Liste erscheint „Passwort: •••••••• [anzeigen]"; Klick auf „anzeigen" zeigt das Klartext-Passwort, „verbergen" maskiert wieder. Bestehende Alt-Benutzer (vor der Umstellung, sofern vorhanden) zeigen „— (vor Umstellung gesetzt)". Nach „Bearbeiten" → neues Passwort setzen wird das neue Passwort sichtbar.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/views/admin_benutzer.js
git commit -m "feat(frontend): Klartext-Passwort-Anzeige mit Toggle in Benutzerverwaltung"
```

---

## Abschluss-Checks (nach allen Tasks)

- [ ] **JS-Tests gesamt:** `node --test 'tests/js/*.test.mjs'` → alle grün (parse_scan + filter).
- [ ] **Python-Tests gesamt:** `source ~/.venvs/werkzeug/bin/activate && pytest -q` → alle grün.
- [ ] **Manueller End-to-End-Durchlauf** als Nicht-Admin (Geräte-Übersicht) und als Admin (Maschinenliste + Passwort-Anzeige).
- [ ] **Branch-Status prüfen** und Abschluss über `superpowers:finishing-a-development-branch` (Merge/PR/Deploy entscheiden). Beim Deploy den `ALTER TABLE`-Schritt aus Task 5 nicht vergessen.
