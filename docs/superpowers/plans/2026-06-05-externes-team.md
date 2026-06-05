# Ausleihen für externes Montageteam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim Ausleihen wird abgefragt „Für mich / Für externes Montageteam"; bei einem Team wird der Name erfasst, automatisch in einer Tabelle gemerkt und in der Admin-Historie angezeigt.

**Architecture:** Neue Tabelle `externe_teams` (eindeutiger Name). Die `Ausleihe` referenziert per nullable FK `externes_team_id` ein Team (`NULL` = für den ausleihenden Mitarbeiter). Beim Ausleihen wird ein angegebener Name per find-or-create übernommen. Ein neuer GET-Endpunkt speist das Dropdown; der Ausleih-Dialog im Frontend kombiniert Empfänger- und Zubehör-Auswahl.

**Tech Stack:** FastAPI, SQLAlchemy (declarative), Pydantic v2, SQLite, Vanilla-JS-Frontend, pytest + TestClient.

**Spec:** `docs/superpowers/specs/2026-06-05-externes-team-design.md`

---

## Dateiübersicht

| Datei | Verantwortung | Aktion |
|-------|---------------|--------|
| `backend/models.py` | Tabelle `ExternesTeam` + FK/Relationship/Property an `Ausleihe` | Modify |
| `backend/schemas.py` | `AusleihenRequest` erweitern, `AusleiheHistorieOut` erweitern | Modify |
| `backend/routers/maschinen_router.py` | find-or-create beim Ausleihen + GET `/externe-teams` | Modify |
| `frontend/js/views/maschine.js` | kombinierter Ausleih-Dialog (Empfänger + Zubehör) | Modify |
| `frontend/js/views/admin_historie.js` | Team-Name pro Eintrag anzeigen | Modify |
| `tests/test_externes_team.py` | alle automatisierten Tests | Create |

**Test-Befehl (immer aus dem Projekt-Root):**
```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```

---

## Task 1: Datenmodell `ExternesTeam` + Verknüpfung an `Ausleihe`

**Files:**
- Modify: `backend/models.py` (neue Klasse nach `AusleiheZubehoer`; FK + Relationship + Property in `Ausleihe`)
- Create: `tests/test_externes_team.py`

- [ ] **Step 1: Failing test schreiben**

Neue Datei `tests/test_externes_team.py`:

```python
"""Tests für Ausleihen an externe Montageteams (To-Do Punkt 4)."""

from backend.models import (
    Ausleihe,
    ExternesTeam,
    Maschine,
    MaschinenStatus,
    Rolle,
)

from .conftest import auth_header, make_user


def _maschine(db, code="M-0001"):
    m = Maschine(maschinen_code=code, name="Bohrmaschine",
                 status=MaschinenStatus.VERFUEGBAR)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_modell_team_verknuepfung(db):
    user = make_user(db, "max")
    m = _maschine(db)
    ausleihe = Ausleihe(maschine_id=m.id, benutzer_id=user.id)
    ausleihe.externes_team = ExternesTeam(name="Team Müller")
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert ausleihe.externes_team_id is not None
    assert ausleihe.externes_team_name == "Team Müller"


def test_modell_ohne_team_ist_none(db):
    user = make_user(db, "max")
    m = _maschine(db)
    ausleihe = Ausleihe(maschine_id=m.id, benutzer_id=user.id)
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert ausleihe.externes_team_id is None
    assert ausleihe.externes_team_name is None
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```
Expected: FAIL mit `ImportError: cannot import name 'ExternesTeam'`.

- [ ] **Step 3: Modell implementieren**

In `backend/models.py`, direkt **nach** der `AusleiheZubehoer`-Klasse (vor dem `#  Datenbank-Setup`-Kommentarblock) einfügen:

```python
# --------------------------------------------------------------------
#  ExternesTeam - externe Montageteams (Empfänger einer Ausleihe)
# --------------------------------------------------------------------

class ExternesTeam(Base):
    """Externes Montageteam, für das eine Maschine ausgeliehen werden kann.

    Wird beim Ausleihen automatisch angelegt (find-or-create), sobald ein
    neuer Team-Name verwendet wird. Der eindeutige Name speist das Dropdown.
    """
    __tablename__ = "externe_teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True, index=True)

    ausleihen = relationship("Ausleihe", back_populates="externes_team")

    def __repr__(self) -> str:
        return f"<ExternesTeam '{self.name}'>"
```

Außerdem in der `Ausleihe`-Klasse, **nach** dem `mitgenommenes_zubehoer`-Relationship-Block (vor `@property def ist_offen`), ergänzen:

```python
    # Empfänger: NULL = für den ausleihenden Mitarbeiter selbst;
    # gesetzt = für ein externes Montageteam.
    externes_team_id = Column(
        Integer, ForeignKey("externe_teams.id"), nullable=True, index=True
    )
    externes_team = relationship("ExternesTeam", back_populates="ausleihen")

    @property
    def externes_team_name(self) -> str | None:
        return self.externes_team.name if self.externes_team else None
```

- [ ] **Step 4: Test laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```
Expected: beide Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_externes_team.py
git commit -m "Modell: ExternesTeam + FK an Ausleihe (To-Do Punkt 4)"
```

---

## Task 2: Ausleihen erfasst externes Team (find-or-create)

**Files:**
- Modify: `backend/schemas.py` (`AusleihenRequest`)
- Modify: `backend/routers/maschinen_router.py` (Import + `maschine_ausleihen`)
- Modify: `tests/test_externes_team.py` (Tests anhängen)

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_externes_team.py` anhängen:

```python
def test_ausleihen_fuer_mich_kein_team(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={}, headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(ExternesTeam).count() == 0
    assert db.query(Ausleihe).one().externes_team_id is None


def test_ausleihen_fuer_team_legt_team_an(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"externes_team": "Team Müller"},
                    headers=auth_header(user))

    assert r.status_code == 200
    team = db.query(ExternesTeam).one()
    assert team.name == "Team Müller"
    assert db.query(Ausleihe).one().externes_team_id == team.id


def test_ausleihen_gleicher_team_name_kein_duplikat(client, db):
    user = make_user(db, "max")
    m1 = _maschine(db, code="M-0001")
    m2 = _maschine(db, code="M-0002")

    for m in (m1, m2):
        r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                        json={"externes_team": "Team Müller"},
                        headers=auth_header(user))
        assert r.status_code == 200

    assert db.query(ExternesTeam).count() == 1
    team_ids = {a.externes_team_id for a in db.query(Ausleihe).all()}
    assert len(team_ids) == 1 and None not in team_ids


def test_ausleihen_team_whitespace_ist_fuer_mich(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"externes_team": "   "},
                    headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(ExternesTeam).count() == 0
    assert db.query(Ausleihe).one().externes_team_id is None


def test_ausleihen_ohne_feld_abwaertskompatibel(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"zubehoer_bezeichnungen": []},
                    headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(Ausleihe).one().externes_team_id is None
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v -k "team or mich or abwaerts"
```
Expected: `test_ausleihen_fuer_team_legt_team_an`, `test_ausleihen_gleicher_team_name_kein_duplikat` FAILen (Feld unbekannt / kein Team angelegt). Die „für mich"/whitespace/abwärts-Tests können bereits grün sein.

- [ ] **Step 3: Schema erweitern**

In `backend/schemas.py`, `AusleihenRequest` ersetzen durch:

```python
class AusleihenRequest(BaseModel):
    """Beim Ausleihen mitgenommenes Zubehör + optionaler externer Empfänger."""
    zubehoer_bezeichnungen: list[str] = []
    # None/leer = für den ausleihenden Mitarbeiter; sonst Name des externen Teams.
    externes_team: Optional[str] = None
```

- [ ] **Step 4: Import + Endpunkt erweitern**

In `backend/routers/maschinen_router.py` den `from backend.models import (...)`-Block um `ExternesTeam` ergänzen:

```python
from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Benutzer,
    ExternesTeam,
    Maschine,
    MaschinenStatus,
    Rolle,
    RueckgabeZustand,
    get_db,
)
```

In `maschine_ausleihen`, **nach** dem `ungueltig`-Validierungsblock (der mit `raise HTTPException(... "Unbekanntes Zubehör" ...)` endet) und **vor** `neue_ausleihe = Ausleihe(...)`, einfügen:

```python
    team_name = ((daten.externes_team if daten else None) or "").strip()
    externes_team = None
    if team_name:
        externes_team = (
            db.query(ExternesTeam).filter(ExternesTeam.name == team_name).first()
        )
        if externes_team is None:
            externes_team = ExternesTeam(name=team_name)
            db.add(externes_team)
            db.flush()  # vergibt die id für die FK
```

Den `Ausleihe(...)`-Konstruktor um die FK erweitern:

```python
    neue_ausleihe = Ausleihe(
        maschine_id=maschine.id,
        benutzer_id=current_user.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
        externes_team_id=externes_team.id if externes_team else None,
    )
```

- [ ] **Step 5: Tests laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```
Expected: alle bisherigen Tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py backend/routers/maschinen_router.py tests/test_externes_team.py
git commit -m "Feature: Ausleihen erfasst externes Montageteam (find-or-create)"
```

---

## Task 3: GET-Endpunkt für bekannte Teams

**Files:**
- Modify: `backend/routers/maschinen_router.py` (neuer Endpunkt)
- Modify: `tests/test_externes_team.py` (Tests anhängen)

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_externes_team.py` anhängen:

```python
def test_externe_teams_liste_distinct_sortiert(client, db):
    user = make_user(db, "max")
    m1 = _maschine(db, code="M-0001")
    m2 = _maschine(db, code="M-0002")
    client.post(f"/api/maschinen/{m1.id}/ausleihen",
                json={"externes_team": "Zeta-Bau"}, headers=auth_header(user))
    client.post(f"/api/maschinen/{m2.id}/ausleihen",
                json={"externes_team": "Alpha-Montage"}, headers=auth_header(user))

    r = client.get("/api/maschinen/externe-teams", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json() == ["Alpha-Montage", "Zeta-Bau"]


def test_externe_teams_leer(client, db):
    user = make_user(db, "max")

    r = client.get("/api/maschinen/externe-teams", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v -k externe_teams
```
Expected: `test_externe_teams_liste_distinct_sortiert` FAILt (404 / Route fehlt). `test_externe_teams_leer` kann ebenfalls FAILen (404).

- [ ] **Step 3: Endpunkt implementieren**

In `backend/routers/maschinen_router.py`, **direkt nach** der Funktion `meine_ausleihen` (vor `maschine_per_code`), einfügen:

```python
@router.get("/externe-teams", response_model=list[str])
def externe_teams(
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Liefert die bekannten externen Montageteam-Namen (alphabetisch) fürs Dropdown."""
    zeilen = db.query(ExternesTeam.name).order_by(ExternesTeam.name).all()
    return [z[0] for z in zeilen]
```

(Die statische Route `/externe-teams` kollidiert nicht mit `/by-code/{...}` oder `/{maschine_id}/...`, da kein Pfadparameter auf erster Ebene existiert. `ExternesTeam` wurde bereits in Task 2 importiert.)

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```
Expected: alle Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/maschinen_router.py tests/test_externes_team.py
git commit -m "API: GET /externe-teams für Team-Dropdown"
```

---

## Task 4: Team-Name in der Admin-Historie-Antwort

**Files:**
- Modify: `backend/schemas.py` (`AusleiheHistorieOut`)
- Modify: `tests/test_externes_team.py` (Tests anhängen)

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_externes_team.py` anhängen:

```python
def test_historie_enthaelt_externes_team_name(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN)
    user = make_user(db, "max")
    m = _maschine(db)
    client.post(f"/api/maschinen/{m.id}/ausleihen",
                json={"externes_team": "Team Müller"}, headers=auth_header(user))

    r = client.get(f"/api/admin/maschinen/{m.id}/historie",
                   headers=auth_header(admin))

    assert r.status_code == 200
    eintraege = r.json()
    assert len(eintraege) == 1
    assert eintraege[0]["externes_team_name"] == "Team Müller"


def test_historie_ohne_team_ist_null(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN)
    user = make_user(db, "max")
    m = _maschine(db)
    client.post(f"/api/maschinen/{m.id}/ausleihen",
                json={}, headers=auth_header(user))

    r = client.get(f"/api/admin/maschinen/{m.id}/historie",
                   headers=auth_header(admin))

    assert r.status_code == 200
    assert r.json()[0]["externes_team_name"] is None
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v -k historie
```
Expected: `test_historie_enthaelt_externes_team_name` FAILt (Feld fehlt im JSON / `KeyError`).

- [ ] **Step 3: Schema erweitern**

In `backend/schemas.py`, `AusleiheHistorieOut` um ein Feld ergänzen (nach `ist_offen: bool`):

```python
class AusleiheHistorieOut(_ORM):
    """Eintrag in der Maschinen-Historie (Admin)."""
    id: int
    benutzer: BenutzerKurz
    ausleih_zeitpunkt: datetime
    rueckgabe_zeitpunkt: Optional[datetime] = None
    rueckgabe_zustand: Optional[RueckgabeZustand] = None
    rueckgabe_kommentar: Optional[str] = None
    dauer_tage: int
    ist_offen: bool
    externes_team_name: Optional[str] = None
```

(Das Feld wird von Pydantic aus der gleichnamigen `Ausleihe.externes_team_name`-Property gelesen — `_ORM` hat `from_attributes=True`.)

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_externes_team.py -v
```
Expected: alle Tests PASS.

- [ ] **Step 5: Gesamte Test-Suite laufen lassen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest -v
```
Expected: alle Tests (inkl. `test_zubehoer_protokoll.py`, `test_benutzer_loeschen.py`) PASS — keine Regression.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py tests/test_externes_team.py
git commit -m "API: externes_team_name in Historie-Antwort"
```

---

## Task 5: Frontend — kombinierter Ausleih-Dialog

**Files:**
- Modify: `frontend/js/views/maschine.js` (`ausleihenKlick`; `ausleihZubehoerModal` → `ausleihDialog`)

Kein automatisierter Test (Vanilla-JS ohne Test-Harness) — manuelle Verifikation in Task 7.

- [ ] **Step 1: `ausleihenKlick` ersetzen**

Bestehende Funktion `ausleihenKlick` (innerhalb `renderMaschine`) ersetzen durch:

```javascript
  async function ausleihenKlick() {
    let teams = [];
    try {
      teams = await api.get('/api/maschinen/externe-teams');
    } catch {
      teams = [];  // Dropdown bleibt leer; freie Eingabe weiterhin möglich
    }
    const auswahl = await ausleihDialog(maschine.zubehoer_liste, teams);
    if (auswahl === null) return;  // abgebrochen
    try {
      maschine = await api.post(`/api/maschinen/${maschine.id}/ausleihen`, auswahl);
      toast('Maschine erfolgreich ausgeliehen.', 'success');
      zeichne();
    } catch (err) {
      toast(err.detail || 'Fehler beim Ausleihen.', 'error');
    }
  }
```

- [ ] **Step 2: `ausleihZubehoerModal` durch `ausleihDialog` ersetzen**

Die modul-weite Funktion `ausleihZubehoerModal` (außerhalb von `renderMaschine`) komplett ersetzen durch:

```javascript
async function ausleihDialog(zubehoerListe, bekannteTeams = []) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm font-medium text-slate-700 mb-2">Für wen leihst du aus?</p>
    <div class="space-y-2 mb-3">
      <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
        <input type="radio" name="empf" value="mich" checked class="w-5 h-5">
        <span class="font-medium">Für mich</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
        <input type="radio" name="empf" value="team" class="w-5 h-5">
        <span class="font-medium">Für externes Montageteam</span>
      </label>
    </div>
    <div id="team-feld" class="mb-4 hidden">
      <label class="block text-sm font-medium text-slate-700 mb-1" for="team-name">Team-Name</label>
      <input id="team-name" list="team-liste" autocomplete="off"
             class="w-full border border-slate-300 rounded-lg p-2 text-sm"
             placeholder="Team auswählen oder neu eingeben">
      <datalist id="team-liste">
        ${bekannteTeams.map((t) => `<option value="${escapeHtml(t)}"></option>`).join('')}
      </datalist>
      <p id="team-fehler" class="text-sm text-rose-600 mt-1 hidden">
        Bitte einen Team-Namen eingeben.
      </p>
    </div>
    ${zubehoerListe.length ? `
      <p class="text-sm text-slate-600 mb-2">Welches Zubehör nimmst du mit? Hake an, was du mitnimmst.</p>
      <div class="space-y-2">
        ${zubehoerListe.map((z) => `
          <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
            <input type="checkbox" value="${escapeHtml(z.bezeichnung)}" class="w-5 h-5">
            <span class="font-medium">${escapeHtml(z.bezeichnung)}</span>
          </label>`).join('')}
      </div>` : ''}`;

  // Team-Eingabefeld nur zeigen, wenn "externes Montageteam" gewählt ist.
  body.querySelectorAll('input[name=empf]').forEach((r) => {
    r.addEventListener('change', () => {
      const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
      body.querySelector('#team-feld').classList.toggle('hidden', !istTeam);
    });
  });

  const result = await modal({
    titel: 'Maschine ausleihen',
    body,
    buttons: [
      {
        label: 'Ausleihen',
        variant: 'success',
        value: 'go',
        onClick: () => {
          body.querySelector('#team-fehler').classList.add('hidden');
          const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
          if (istTeam && !body.querySelector('#team-name').value.trim()) {
            body.querySelector('#team-fehler').classList.remove('hidden');
            body.querySelector('#team-name').focus();
            return false;  // Modal offen lassen
          }
          return true;
        },
      },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go') return null;

  const istTeam = body.querySelector('input[name=empf]:checked').value === 'team';
  const externes_team = istTeam ? body.querySelector('#team-name').value.trim() : null;

  const zubehoer_bezeichnungen = [...body.querySelectorAll('input[type=checkbox]:checked')]
    .map((c) => c.value);

  if (zubehoerListe.length && zubehoer_bezeichnungen.length === 0) {
    const ok = await confirmDialog('Wirklich ohne Zubehör ausleihen?', {
      titel: 'Ohne Zubehör?',
      okLabel: 'Ja, ohne Zubehör',
    });
    if (!ok) return null;
  }
  return { zubehoer_bezeichnungen, externes_team };
}
```

(`escapeHtml`, `modal`, `confirmDialog`, `toast` sind bereits oben in `maschine.js` importiert — kein neuer Import nötig.)

- [ ] **Step 3: Commit**

```bash
git add frontend/js/views/maschine.js
git commit -m "Frontend: kombinierter Ausleih-Dialog (Empfänger + Zubehör)"
```

---

## Task 6: Frontend — Team-Name in der Admin-Historie

**Files:**
- Modify: `frontend/js/views/admin_historie.js`

- [ ] **Step 1: Empfänger-Zeile erweitern**

In `frontend/js/views/admin_historie.js` die Zeile mit dem Benutzernamen

```javascript
                <div class="font-medium text-slate-900">${escapeHtml(e.benutzer.voller_name)}</div>
```

ersetzen durch:

```javascript
                <div class="font-medium text-slate-900">${escapeHtml(e.benutzer.voller_name)}${
                  e.externes_team_name
                    ? ` <span class="font-normal text-slate-500">für</span> ${escapeHtml(e.externes_team_name)}`
                    : ''
                }</div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/views/admin_historie.js
git commit -m "Frontend: externes Team in der Admin-Historie anzeigen"
```

---

## Task 7: Manuelle Verifikation & Abschluss

**Files:** keine Änderung (nur Prüfen).

- [ ] **Step 1: Server starten**

```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app && \
~/.venvs/werkzeug/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- [ ] **Step 2: Durchspielen (Browser auf http://127.0.0.1:8000)**

Als `max.mueller` / `test1234` einloggen:
1. Maschine **mit** Zubehör öffnen → `AUSLEIHEN`: Dialog zeigt oben „Für mich" (vorausgewählt) / „Für externes Montageteam", darunter die Zubehör-Auswahl.
2. „Für externes Montageteam" wählen → Eingabefeld erscheint; Dropdown listet bereits verwendete Teams, freie Eingabe möglich. Leer lassen + `Ausleihen` → Inline-Hinweis „Bitte einen Team-Namen eingeben.", Dialog bleibt offen.
3. Neuen Namen eingeben + ausleihen → Maschine ausgeliehen.
4. Maschine zurückgeben, erneut ausleihen → der zuvor eingegebene Name steht jetzt im Dropdown.
5. Maschine **ohne** Zubehör → `AUSLEIHEN` zeigt nur die Empfänger-Abfrage (kein Zubehör-Block).
6. Als Admin die **Historie** der Maschine öffnen → Eintrag zeigt „[Mitarbeiter] für [Team]"; bei „für mich"-Ausleihen nur der Mitarbeiter.

- [ ] **Step 3: Gesamte Test-Suite final**

```bash
~/.venvs/werkzeug/bin/python -m pytest -v
```
Expected: alle Tests grün.

- [ ] **Step 4: Deploy-Hinweis**

Nach erfolgreicher manueller Prüfung: `git push`, dann `./deploy.sh --go` (etablierter Workflow). Die neue Tabelle `externe_teams` legt `create_all` beim Server-Start automatisch an — kein manueller DB-Eingriff nötig.

---

## Self-Review-Notiz (vom Plan-Autor)

- **Spec-Abdeckung:** Datenmodell + FK (T1), Ausleih-Erfassung mit find-or-create inkl. „für mich"/Whitespace/Duplikat/Abwärtskompatibilität (T2), Dropdown-Endpunkt (T3), Historie-Feld (T4), kombinierter Dialog mit Datalist + Validierung + „ohne Zubehör"-Rückfrage (T5), Historie-Anzeige (T6), manuelle Verifikation aller Flows (T7). Alle Spec-Punkte sind Tasks zugeordnet; bewusst ausgelassene Punkte (keine Team-Verwaltung, keine Anzeige in „Meine Ausleihen"/Detailseite) bleiben außen vor.
- **Typen-Konsistenz:** Request-Feld `externes_team` (Backend `daten.externes_team`, Frontend-Payload `externes_team`), Property/Schema/JSON `externes_team_name` (Model-Property, `AusleiheHistorieOut`, Frontend `e.externes_team_name`), Endpunkt `GET /api/maschinen/externe-teams` (Backend-Route + Frontend `api.get`) durchgängig gleich benannt. FK-Spalte/Relationship `externes_team_id`/`externes_team`.
