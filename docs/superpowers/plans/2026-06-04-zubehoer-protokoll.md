# Pflicht-Zubehör beim Ausleihen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim Ausleihen erfassen, welches Zubehör mitgenommen wurde; bei der Rückgabe abhaken und Fehlendes vermerken.

**Architecture:** Neue Kind-Tabelle `ausleihe_zubehoer` speichert pro Ausleihe einen unveränderlichen Schnappschuss der mitgenommenen Zubehör-Namen plus ein `zurueckgebracht`-Flag. Die zwei bestehenden Endpunkte (Ausleihen/Rückgabe) werden erweitert; das Frontend bekommt je einen Dialog. `create_all` legt die Tabelle beim Server-Start automatisch an — keine Migration.

**Tech Stack:** FastAPI, SQLAlchemy (declarative), Pydantic v2, SQLite, Vanilla-JS-Frontend, pytest + TestClient.

**Spec:** `docs/superpowers/specs/2026-06-04-zubehoer-protokoll-design.md`

---

## Dateiübersicht

| Datei | Verantwortung | Aktion |
|-------|---------------|--------|
| `backend/models.py` | Tabelle `AusleiheZubehoer` + Relationship an `Ausleihe` | Modify |
| `backend/schemas.py` | Request-/Response-Schemas | Modify |
| `backend/routers/maschinen_router.py` | Ausleih- + Rückgabe-Logik | Modify |
| `frontend/js/views/maschine.js` | Ausleih-Dialog + Rückgabe-Dialog | Modify |
| `tests/test_zubehoer_protokoll.py` | alle automatisierten Tests | Create |

**Test-Befehl (immer aus dem Projekt-Root):**
```bash
cd /media/sf_claude_project/Verwaltungssystem-Maschinen/werkzeug_app
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v
```

---

## Task 1: Datenmodell `AusleiheZubehoer`

**Files:**
- Modify: `backend/models.py` (neue Klasse nach `Ausleihe`, neues Relationship in `Ausleihe`)
- Create: `tests/test_zubehoer_protokoll.py`

- [ ] **Step 1: Failing test schreiben**

Neue Datei `tests/test_zubehoer_protokoll.py`:

```python
"""Tests für Zubehör-Mitnahme-Protokoll (To-Do Punkt 1)."""

from datetime import datetime, timezone

from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Maschine,
    MaschinenStatus,
)

from .conftest import auth_header, make_user


def _maschine_mit_zubehoer(db, code="M-0001", teile=("Akku", "Ladegerät")):
    from backend.models import Zubehoer
    m = Maschine(maschinen_code=code, name="Bohrmaschine",
                 status=MaschinenStatus.VERFUEGBAR)
    for t in teile:
        m.zubehoer_liste.append(Zubehoer(bezeichnung=t))
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_modell_speichert_und_cascade_loescht(db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db)
    ausleihe = Ausleihe(
        maschine_id=m.id,
        benutzer_id=user.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
    )
    ausleihe.mitgenommenes_zubehoer.append(AusleiheZubehoer(bezeichnung="Akku"))
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert len(ausleihe.mitgenommenes_zubehoer) == 1
    zeile = ausleihe.mitgenommenes_zubehoer[0]
    assert zeile.bezeichnung == "Akku"
    assert zeile.zurueckgebracht is None

    # Cascade: Ausleihe löschen entfernt die Zubehör-Zeile
    db.delete(ausleihe)
    db.commit()
    assert db.query(AusleiheZubehoer).count() == 0
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py::test_modell_speichert_und_cascade_loescht -v
```
Expected: FAIL mit `ImportError: cannot import name 'AusleiheZubehoer'`.

- [ ] **Step 3: Modell implementieren**

In `backend/models.py`, direkt **nach** der `Ausleihe`-Klasse (vor dem `Datenbank-Setup`-Block) einfügen:

```python
# --------------------------------------------------------------------
#  AusleiheZubehoer - Mitnahme-Protokoll pro Ausleihe
# --------------------------------------------------------------------

class AusleiheZubehoer(Base):
    """Schnappschuss eines beim Ausleihen mitgenommenen Zubehörteils.

    Der Name wird kopiert (nicht per FK verlinkt), damit das Protokoll
    unveränderlich bleibt, auch wenn der Admin das Zubehör der Maschine
    später ändert oder löscht.
    """
    __tablename__ = "ausleihe_zubehoer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ausleihe_id = Column(
        Integer,
        ForeignKey("ausleihen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bezeichnung = Column(String(120), nullable=False)
    # NULL = Rückgabe noch offen; True/False wird bei der Rückgabe gesetzt
    zurueckgebracht = Column(Boolean, nullable=True)

    ausleihe = relationship("Ausleihe", back_populates="mitgenommenes_zubehoer")

    def __repr__(self) -> str:
        return f"<AusleiheZubehoer '{self.bezeichnung}'>"
```

Außerdem in der `Ausleihe`-Klasse, bei den Beziehungen (nach `benutzer = relationship(...)`), ergänzen:

```python
    mitgenommenes_zubehoer = relationship(
        "AusleiheZubehoer",
        back_populates="ausleihe",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 4: Test laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py::test_modell_speichert_und_cascade_loescht -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py tests/test_zubehoer_protokoll.py
git commit -m "Modell: AusleiheZubehoer (Mitnahme-Protokoll)"
```

---

## Task 2: Ausleihen erfasst mitgenommenes Zubehör

**Files:**
- Modify: `backend/schemas.py` (neues `AusleihenRequest`)
- Modify: `backend/routers/maschinen_router.py` (`maschine_ausleihen`)
- Modify: `tests/test_zubehoer_protokoll.py` (Tests 1–4)

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_zubehoer_protokoll.py` anhängen:

```python
def test_ausleihen_speichert_angehakte_teile(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku", "Ladegerät", "Koffer"))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku", "Koffer"]},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeilen = db.query(AusleiheZubehoer).all()
    assert sorted(z.bezeichnung for z in zeilen) == ["Akku", "Koffer"]
    assert all(z.zurueckgebracht is None for z in zeilen)


def test_ausleihen_mit_leerer_liste(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db)

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": []},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    assert db.query(AusleiheZubehoer).count() == 0
    db.refresh(m)
    assert m.status == MaschinenStatus.AUSGELIEHEN


def test_ausleihen_unbekannte_bezeichnung_400(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku", "Phantom-Teil"]},
        headers=auth_header(user),
    )

    assert r.status_code == 400
    assert db.query(Ausleihe).count() == 0
    db.refresh(m)
    assert m.status == MaschinenStatus.VERFUEGBAR


def test_protokoll_ist_schnappschuss(client, db):
    from backend.models import Zubehoer
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku"]},
        headers=auth_header(user),
    )
    assert r.status_code == 200

    # Admin entfernt das Zubehör der Maschine komplett
    db.query(Zubehoer).filter(Zubehoer.maschine_id == m.id).delete()
    db.commit()

    zeile = db.query(AusleiheZubehoer).one()
    assert zeile.bezeichnung == "Akku"  # Protokoll unverändert
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v -k "ausleihen or schnappschuss"
```
Expected: Die vier neuen Tests FAILen (validierung/speicherung fehlt; unbekannte Bezeichnung gibt aktuell noch 200).

- [ ] **Step 3: Schema ergänzen**

In `backend/schemas.py`, im Abschnitt `Ausleihe` (vor `ZurueckgabeRequest`), einfügen:

```python
class AusleihenRequest(BaseModel):
    """Beim Ausleihen mitgenommenes Zubehör (Bezeichnungen aus der Maschinen-Liste)."""
    zubehoer_bezeichnungen: list[str] = []
```

- [ ] **Step 4: Endpunkt erweitern**

In `backend/routers/maschinen_router.py`:

Import-Block um `AusleiheZubehoer` und `AusleihenRequest` erweitern:

```python
from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Benutzer,
    Maschine,
    MaschinenStatus,
    Rolle,
    RueckgabeZustand,
    get_db,
)
from backend.schemas import (
    AusleihenRequest,
    MaschineOut,
    MeineAusleiheOut,
    ZurueckgabeRequest,
)
```

`maschine_ausleihen` wird zu (Signatur um optionalen Body erweitert, Validierung + Speichern vor `db.commit()`):

```python
@router.post("/{maschine_id}/ausleihen", response_model=MaschineOut)
def maschine_ausleihen(
    maschine_id: int,
    daten: AusleihenRequest | None = None,
    current_user: Benutzer = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaschineOut:
    """Übernimmt eine Maschine in die eigene Ausleihe.

    Voraussetzungen: Maschine existiert und hat Status 'verfuegbar'.
    Optional wird das mitgenommene Zubehör protokolliert.
    """
    maschine = db.query(Maschine).filter(Maschine.id == maschine_id).first()
    if maschine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maschine nicht gefunden.",
        )

    if maschine.status != MaschinenStatus.VERFUEGBAR:
        meldungen = {
            MaschinenStatus.AUSGELIEHEN: "Maschine ist bereits ausgeliehen.",
            MaschinenStatus.DEFEKT: "Maschine ist als defekt gemeldet und muss vom Admin freigegeben werden.",
            MaschinenStatus.WARTUNG: "Maschine ist in Wartung und muss vom Admin freigegeben werden.",
        }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=meldungen.get(maschine.status, "Maschine ist nicht verfügbar."),
        )

    bezeichnungen = daten.zubehoer_bezeichnungen if daten else []
    gueltige = {z.bezeichnung for z in maschine.zubehoer_liste}
    ungueltig = [b for b in bezeichnungen if b not in gueltige]
    if ungueltig:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unbekanntes Zubehör: {', '.join(ungueltig)}",
        )

    neue_ausleihe = Ausleihe(
        maschine_id=maschine.id,
        benutzer_id=current_user.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
    )
    for bezeichnung in bezeichnungen:
        neue_ausleihe.mitgenommenes_zubehoer.append(
            AusleiheZubehoer(bezeichnung=bezeichnung)
        )
    maschine.status = MaschinenStatus.AUSGELIEHEN
    db.add(neue_ausleihe)
    db.commit()
    db.refresh(maschine)
    return maschine_zu_out(maschine, current_user.id)
```

- [ ] **Step 5: Tests laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v
```
Expected: alle bisherigen Tests PASS (Modell-Test + 4 Ausleih-Tests).

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py backend/routers/maschinen_router.py tests/test_zubehoer_protokoll.py
git commit -m "Feature: Ausleihen protokolliert mitgenommenes Zubehör"
```

---

## Task 3: Rückgabe gleicht Zubehör ab

**Files:**
- Modify: `backend/schemas.py` (`ZurueckgabeRequest` erweitern)
- Modify: `backend/routers/maschinen_router.py` (`maschine_zurueckgeben`)
- Modify: `tests/test_zubehoer_protokoll.py` (Tests 5–7)

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_zubehoer_protokoll.py` anhängen:

```python
def _ausleihen_mit_zubehoer(client, db, user, teile, mitnehmen):
    m = _maschine_mit_zubehoer(db, teile=teile)
    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": list(mitnehmen)},
        headers=auth_header(user),
    )
    assert r.status_code == 200
    return m


def test_rueckgabe_alles_zurueck(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku", "Ladegerät"), ("Akku", "Ladegerät"))
    ids = [z.id for z in db.query(AusleiheZubehoer).all()]

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": None,
              "zurueckgebrachte_zubehoer_ids": ids},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeilen = db.query(AusleiheZubehoer).all()
    assert all(z.zurueckgebracht is True for z in zeilen)
    ausleihe = db.query(Ausleihe).one()
    assert "Nicht zurückgegeben" not in (ausleihe.rueckgabe_kommentar or "")


def test_rueckgabe_mit_fehlendem_teil(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku", "Ladegerät"), ("Akku", "Ladegerät"))
    akku = db.query(AusleiheZubehoer).filter_by(bezeichnung="Akku").one()

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": "alles gut",
              "zurueckgebrachte_zubehoer_ids": [akku.id]},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    db.expire_all()
    akku = db.query(AusleiheZubehoer).filter_by(bezeichnung="Akku").one()
    lader = db.query(AusleiheZubehoer).filter_by(bezeichnung="Ladegerät").one()
    assert akku.zurueckgebracht is True
    assert lader.zurueckgebracht is False
    ausleihe = db.query(Ausleihe).one()
    assert "Ladegerät" in ausleihe.rueckgabe_kommentar
    assert "Nicht zurückgegeben" in ausleihe.rueckgabe_kommentar
    assert "alles gut" in ausleihe.rueckgabe_kommentar  # Originalkommentar bleibt


def test_rueckgabe_ohne_feld_abwaertskompatibel(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku",), ("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": None},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeile = db.query(AusleiheZubehoer).one()
    assert zeile.zurueckgebracht is True
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v -k rueckgabe
```
Expected: die drei Rückgabe-Tests FAILen (Feld unbekannt / `zurueckgebracht` bleibt None).

- [ ] **Step 3: Schema erweitern**

In `backend/schemas.py`, `ZurueckgabeRequest` ersetzen durch:

```python
class ZurueckgabeRequest(BaseModel):
    zustand: RueckgabeZustand
    kommentar: Optional[str] = None
    # IDs der AusleiheZubehoer-Zeilen, die zurückkamen.
    # None = altes Verhalten: alles gilt als zurückgebracht.
    zurueckgebrachte_zubehoer_ids: Optional[list[int]] = None
```

- [ ] **Step 4: Endpunkt erweitern**

In `backend/routers/maschinen_router.py`, in `maschine_zurueckgeben` den Block, der `rueckgabe_*` setzt, ersetzen. Aktuell:

```python
    offene_ausleihe.rueckgabe_zeitpunkt = datetime.now(timezone.utc)
    offene_ausleihe.rueckgabe_zustand = daten.zustand
    offene_ausleihe.rueckgabe_kommentar = daten.kommentar
```

wird zu:

```python
    offene_ausleihe.rueckgabe_zeitpunkt = datetime.now(timezone.utc)
    offene_ausleihe.rueckgabe_zustand = daten.zustand

    kommentar = daten.kommentar
    if daten.zurueckgebrachte_zubehoer_ids is None:
        # Abwärtskompatibel: ohne Angabe gilt alles als zurückgebracht.
        for zeile in offene_ausleihe.mitgenommenes_zubehoer:
            zeile.zurueckgebracht = True
    else:
        zurueck_ids = set(daten.zurueckgebrachte_zubehoer_ids)
        fehlend = []
        for zeile in offene_ausleihe.mitgenommenes_zubehoer:
            zeile.zurueckgebracht = zeile.id in zurueck_ids
            if not zeile.zurueckgebracht:
                fehlend.append(zeile.bezeichnung)
        if fehlend:
            vermerk = "⚠ Nicht zurückgegeben: " + ", ".join(fehlend)
            kommentar = f"{kommentar}\n{vermerk}" if kommentar else vermerk
    offene_ausleihe.rueckgabe_kommentar = kommentar
```

- [ ] **Step 5: Tests laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v
```
Expected: alle Tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py backend/routers/maschinen_router.py tests/test_zubehoer_protokoll.py
git commit -m "Feature: Rückgabe gleicht mitgenommenes Zubehör ab"
```

---

## Task 4: Zubehör-Protokoll in der API-Antwort

**Files:**
- Modify: `backend/schemas.py` (`AusleiheZubehoerOut`, Einbettung in `AusleiheKurz` + `MeineAusleiheOut`)
- Modify: `tests/test_zubehoer_protokoll.py` (Test 8)

- [ ] **Step 1: Failing test schreiben**

In `tests/test_zubehoer_protokoll.py` anhängen:

```python
def test_meine_ausleihen_zeigt_zubehoer(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku", "Ladegerät"), ("Akku",))

    r = client.get("/api/maschinen/meine", headers=auth_header(user))

    assert r.status_code == 200
    eintraege = r.json()
    assert len(eintraege) == 1
    # Die mitgenommene Liste hängt an der Ausleihe selbst:
    mitgenommen = eintraege[0]["mitgenommenes_zubehoer"]
    assert len(mitgenommen) == 1
    assert mitgenommen[0]["bezeichnung"] == "Akku"
    assert mitgenommen[0]["zurueckgebracht"] is None
    assert "id" in mitgenommen[0]
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py::test_meine_ausleihen_zeigt_zubehoer -v
```
Expected: FAIL mit `KeyError: 'mitgenommenes_zubehoer'`.

- [ ] **Step 3: Schemas ergänzen**

In `backend/schemas.py`, im Abschnitt `Zubehör` (nach `ZubehoerCreate`), neues Out-Schema:

```python
class AusleiheZubehoerOut(_ORM):
    id: int
    bezeichnung: str
    zurueckgebracht: Optional[bool] = None
```

In `AusleiheKurz` das Feld ergänzen:

```python
class AusleiheKurz(_ORM):
    """Reduzierte Ausleih-Info, eingebettet in MaschineOut."""
    id: int
    benutzer_id: int
    benutzer: BenutzerKurz
    ausleih_zeitpunkt: datetime
    mitgenommenes_zubehoer: list[AusleiheZubehoerOut] = []
```

In `MeineAusleiheOut` das Feld ergänzen:

```python
class MeineAusleiheOut(_ORM):
    """Offene Ausleihe des aktuellen Mitarbeiters."""
    id: int
    ausleih_zeitpunkt: datetime
    dauer_tage: int
    maschine: MaschineKurz
    mitgenommenes_zubehoer: list[AusleiheZubehoerOut] = []
```

- [ ] **Step 4: Test laufen lassen, Erfolg prüfen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest tests/test_zubehoer_protokoll.py -v
```
Expected: alle Tests PASS.

- [ ] **Step 5: Gesamte Test-Suite laufen lassen**

Run:
```bash
~/.venvs/werkzeug/bin/python -m pytest -v
```
Expected: alle Tests (inkl. `test_benutzer_loeschen.py`) PASS — keine Regression.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py tests/test_zubehoer_protokoll.py
git commit -m "API: Zubehör-Protokoll in Ausleih-Antwort einbetten"
```

---

## Task 5: Frontend — Ausleih-Dialog

**Files:**
- Modify: `frontend/js/views/maschine.js` (`ausleihenKlick`, neue Funktion `ausleihZubehoerModal`, Import)

Kein automatisierter Test (Vanilla-JS ohne Test-Harness) — manuelle Verifikation am Ende.

- [ ] **Step 1: Import erweitern**

In `frontend/js/views/maschine.js` den ui-Import um `confirmDialog` ergänzen:

```javascript
import {
  btnClasses, confirmDialog, escapeHtml, modal, spinner, statusBadge, toast, zeitseit,
} from '../ui.js';
```

- [ ] **Step 2: `ausleihenKlick` ersetzen**

Bestehende Funktion `ausleihenKlick` ersetzen durch:

```javascript
  async function ausleihenKlick() {
    let bezeichnungen = [];
    if (maschine.zubehoer_liste.length) {
      const auswahl = await ausleihZubehoerModal(maschine.zubehoer_liste);
      if (auswahl === null) return;  // abgebrochen
      bezeichnungen = auswahl;
    }
    try {
      maschine = await api.post(`/api/maschinen/${maschine.id}/ausleihen`,
        { zubehoer_bezeichnungen: bezeichnungen });
      toast('Maschine erfolgreich ausgeliehen.', 'success');
      zeichne();
    } catch (err) {
      toast(err.detail || 'Fehler beim Ausleihen.', 'error');
    }
  }
```

- [ ] **Step 3: `ausleihZubehoerModal` hinzufügen**

Als modul-weite Funktion (neben `rueckgabeModal`, außerhalb von `renderMaschine`) einfügen:

```javascript
async function ausleihZubehoerModal(zubehoerListe) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-slate-600 mb-3">Welches Zubehör nimmst du mit? Hake an, was du mitnimmst.</p>
    <div class="space-y-2">
      ${zubehoerListe.map((z) => `
        <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
          <input type="checkbox" value="${escapeHtml(z.bezeichnung)}" class="w-5 h-5">
          <span class="font-medium">${escapeHtml(z.bezeichnung)}</span>
        </label>`).join('')}
    </div>`;

  const result = await modal({
    titel: 'Zubehör mitnehmen',
    body,
    buttons: [
      { label: 'Ausleihen', variant: 'success', value: 'go' },
      { label: 'Abbrechen', variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go') return null;

  const checked = [...body.querySelectorAll('input[type=checkbox]:checked')]
    .map((c) => c.value);

  if (checked.length === 0) {
    const ok = await confirmDialog('Wirklich ohne Zubehör ausleihen?', {
      titel: 'Ohne Zubehör?',
      okLabel: 'Ja, ohne Zubehör',
    });
    if (!ok) return null;
  }
  return checked;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/js/views/maschine.js
git commit -m "Frontend: Zubehör-Auswahl beim Ausleihen"
```

---

## Task 6: Frontend — Rückgabe-Dialog

**Files:**
- Modify: `frontend/js/views/maschine.js` (`zurueckKlick`, `rueckgabeModal`)

- [ ] **Step 1: `zurueckKlick` anpassen**

Bestehende Funktion `zurueckKlick` so ändern, dass sie das mitgenommene Zubehör an `rueckgabeModal` übergibt. Den Anfang:

```javascript
  async function zurueckKlick() {
    const eingabe = await rueckgabeModal();
    if (!eingabe) return;
```

ersetzen durch:

```javascript
  async function zurueckKlick() {
    const mitgenommen =
      (maschine.aktuelle_ausleihe && maschine.aktuelle_ausleihe.mitgenommenes_zubehoer) || [];
    const eingabe = await rueckgabeModal(mitgenommen);
    if (!eingabe) return;
```

(Der Rest der Funktion — `api.post(.../zurueckgeben, eingabe)` etc. — bleibt unverändert.)

- [ ] **Step 2: `rueckgabeModal` erweitern**

`rueckgabeModal()` ersetzen durch die Variante mit Parameter + Zubehör-Abhakliste:

```javascript
async function rueckgabeModal(mitgenommen = []) {
  const body = document.createElement('div');
  body.innerHTML = `
    <p class="text-sm text-slate-600 mb-3">Wie ist der Zustand?</p>
    <div class="space-y-2 mb-4">
      <label class="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
        <input type="radio" name="zust" value="ok" checked class="w-5 h-5">
        <span class="font-medium">Alles in Ordnung</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-rose-200 rounded-lg cursor-pointer hover:bg-rose-50">
        <input type="radio" name="zust" value="defekt" class="w-5 h-5">
        <span class="font-medium text-rose-700">Defekt</span>
      </label>
      <label class="flex items-center gap-3 p-3 border border-amber-200 rounded-lg cursor-pointer hover:bg-amber-50">
        <input type="radio" name="zust" value="wartung" class="w-5 h-5">
        <span class="font-medium text-amber-700">Wartung nötig</span>
      </label>
    </div>
    ${mitgenommen.length ? `
      <div class="mb-4">
        <p class="text-sm font-medium text-slate-700 mb-2">Zubehör zurückgegeben?</p>
        <div class="space-y-2">
          ${mitgenommen.map((z) => `
            <label class="flex items-center gap-3 p-2 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
              <input type="checkbox" data-zid="${z.id}" checked class="w-5 h-5">
              <span class="text-sm">${escapeHtml(z.bezeichnung)}</span>
            </label>`).join('')}
        </div>
      </div>` : ''}
    <label class="block text-sm font-medium text-slate-700 mb-1" for="r-komm">Kommentar (optional)</label>
    <textarea id="r-komm" rows="3"
              class="w-full border border-slate-300 rounded-lg p-2 text-sm"
              placeholder="Was ist passiert?"></textarea>`;

  const result = await modal({
    titel: 'Maschine zurückgeben',
    body,
    buttons: [
      { label: 'Bestätigen', variant: 'primary',   value: 'go' },
      { label: 'Abbrechen',  variant: 'secondary', value: null },
    ],
  });
  if (result !== 'go') return null;

  const zustand   = body.querySelector('input[name=zust]:checked').value;
  const kommentar = body.querySelector('#r-komm').value.trim() || null;

  const result_obj = { zustand, kommentar };
  if (mitgenommen.length) {
    result_obj.zurueckgebrachte_zubehoer_ids =
      [...body.querySelectorAll('input[data-zid]:checked')]
        .map((c) => Number(c.dataset.zid));
  }
  return result_obj;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/js/views/maschine.js
git commit -m "Frontend: Zubehör-Abgleich bei der Rückgabe"
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

Als `max.mueller` / `test1234` einloggen, eine Maschine **mit** Zubehör öffnen:
1. `AUSLEIHEN` → Dialog erscheint mit allen Zubehörteilen, **keins angehakt**.
2. Ein Teil anhaken, `Ausleihen` → Maschine ist ausgeliehen.
3. `ZURÜCKGEBEN` → Rückgabe-Dialog zeigt das mitgenommene Teil **vorab angehakt**.
4. Haken entfernen, `Bestätigen` → in der Admin-Historie steht „⚠ Nicht zurückgegeben: …".
5. Maschine **ohne** Zubehör: `AUSLEIHEN` läuft wie bisher direkt (kein Dialog).
6. Maschine mit Zubehör, beim Ausleihen **nichts** anhaken → Rückfrage „Wirklich ohne Zubehör ausleihen?".

- [ ] **Step 3: Gesamte Test-Suite final**

```bash
~/.venvs/werkzeug/bin/python -m pytest -v
```
Expected: alle Tests grün.

- [ ] **Step 4: Deploy-Hinweis**

Nach erfolgreicher manueller Prüfung: `git push`, dann `./deploy.sh --go` (wie im etablierten Workflow). Die neue Tabelle legt `create_all` beim Server-Start automatisch an — kein manueller DB-Eingriff nötig.

---

## Self-Review-Notiz (vom Plan-Autor)

- Spec-Abdeckung: Datenmodell (T1), Ausleih-Erfassung + leere Liste + Validierung + Schnappschuss (T2), Rückgabe-Abgleich + Vermerk + Abwärtskompatibilität (T3), API-Anzeige (T4), Ausleih-Dialog inkl. „ohne Zubehör"-Rückfrage (T5), Rückgabe-Dialog (T6), manuelle Verifikation aller Spec-Flows (T7). Alle 8 Spec-Tests sind Tasks zugeordnet.
- Typen-Konsistenz: `mitgenommenes_zubehoer` (Relationship + Schema-Feld), `zurueckgebracht`, `zubehoer_bezeichnungen`, `zurueckgebrachte_zubehoer_ids` durchgängig gleich benannt in Backend, Tests und Frontend.
