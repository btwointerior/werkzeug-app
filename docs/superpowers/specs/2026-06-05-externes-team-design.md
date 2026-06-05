# Ausleihen für externes Montageteam — Design (To-Do Punkt 4)

**Status:** Freigegeben (2026-06-05)

## Ziel

Beim Ausleihen einer Maschine wird abgefragt, ob sie **für mich** oder **für ein
externes Montageteam** ausgeliehen wird. Bei „externes Team" wird ein Team-Name
erfasst. Der Empfänger ist in der Admin-Historie sichtbar.

Quelle: To-Do Punkt 4 — „Nach dem Klicken Ausleihen → Abfrage → Für mich / Für
externes Montageteam → Name eintragen".

## Entscheidungen (aus dem Brainstorming)

| Frage | Entscheidung |
|-------|--------------|
| Namens-Eingabe | Dropdown bekannter Teams **+** Freitext für neue |
| Quelle der bekannten Teams | Eigene Tabelle `externe_teams`, **automatisch befüllt** (Ansatz C) |
| Dialog-Ablauf | **Ein kombinierter Dialog** (Empfänger + Zubehör) |
| Anzeige | **Admin-Historie** |

## Architektur

Neue Tabelle `externe_teams` (id, name unique). Die `Ausleihe` referenziert per
nullable FK `externes_team_id` ein Team. **`NULL` = „Für mich"** (der
ausleihende Mitarbeiter `benutzer_id`). Beim Ausleihen wird ein angegebener
Team-Name per **find-or-create** in die Tabelle übernommen — neue Teams „merken"
sich dadurch automatisch, ohne separate Verwaltungsseite. `create_all` legt die
Tabelle beim Server-Start an — keine Migration.

Konsistent zur bestehenden Architektur: kleine, fokussierte Erweiterung der zwei
bestehenden Ausleih-Bausteine (Endpunkt + Dialog), analog zum bereits
umgesetzten Zubehör-Protokoll.

## Datenmodell — `backend/models.py`

Neue Klasse:

```python
class ExternesTeam(Base):
    __tablename__ = "externe_teams"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True, index=True)
    ausleihen = relationship("Ausleihe", back_populates="externes_team")
```

`Ausleihe` ergänzen:

```python
    externes_team_id = Column(
        Integer, ForeignKey("externe_teams.id"), nullable=True, index=True
    )
    externes_team = relationship("ExternesTeam", back_populates="ausleihen")

    @property
    def externes_team_name(self) -> str | None:
        return self.externes_team.name if self.externes_team else None
```

`externes_team_id = NULL` ⇒ Ausleihe für den Mitarbeiter selbst.

## API — `backend/schemas.py`, `backend/routers/maschinen_router.py`

**Schemas:**
- `AusleihenRequest` um optionales Feld erweitern:
  ```python
  class AusleihenRequest(BaseModel):
      zubehoer_bezeichnungen: list[str] = []
      externes_team: Optional[str] = None  # None/leer = für mich
  ```
- `AusleiheHistorieOut` um `externes_team_name: Optional[str] = None` erweitern.

**Endpunkt `maschine_ausleihen`** (`POST /api/maschinen/{id}/ausleihen`):
Nach der bestehenden Zubehör-Validierung, vor `db.commit()`:
- `name = (daten.externes_team or "").strip()` (bzw. `""` wenn kein Body).
- Wenn `name` nicht leer: bestehendes `ExternesTeam` mit diesem Namen suchen;
  fehlt es, neu anlegen (`db.add` + `flush`). `neue_ausleihe.externes_team_id`
  setzen.
- Wenn `name` leer: nichts tun (für mich, `externes_team_id` bleibt `NULL`).

**Neuer Endpunkt** `GET /api/maschinen/externe-teams` (eingeloggte Nutzer):
liefert die nach Name sortierte Liste der Team-Namen (`list[str]`) fürs Dropdown.

## Frontend — `frontend/js/views/maschine.js`

- `ausleihenKlick` öffnet den Dialog **immer** (bisher nur bei vorhandenem
  Zubehör), da der Empfänger stets abgefragt wird.
- Vor dem Öffnen werden die bekannten Teams via
  `api.get('/api/maschinen/externe-teams')` geladen.
- **Kombinierter Dialog** (eine Modal-Instanz), Reihenfolge oben→unten:
  1. Empfänger: Radio „Für mich" (Default) / „Für externes Montageteam".
  2. Bei „externes Team": `<input list="…">` mit `<datalist>` der bekannten
     Teams ⇒ Auswahl bekannter **oder** Eingabe neuer Namen. Das Feld ist nur
     aktiv/relevant, wenn „externes Team" gewählt ist.
  3. Darunter — nur falls `maschine.zubehoer_liste` nicht leer — die bestehende
     Zubehör-Auswahl (unverändert).
- Validierung: „externes Team" gewählt **und** Feld leer ⇒ Inline-Hinweis,
  Dialog bleibt offen.
- Rückgabewert an den Aufruf: `{ zubehoer_bezeichnungen, externes_team }`
  (`externes_team` = `null` bei „für mich").
- Die bestehende „Wirklich ohne Zubehör ausleihen?"-Rückfrage bleibt erhalten.

## Anzeige — `frontend/js/views/admin_historie.js`

Pro Historie-Eintrag: ist `externes_team_name` gesetzt, wird der Empfänger als
„… für **[Team]**" ergänzt; sonst unverändert nur der Mitarbeiter.

## Tests — `tests/test_externes_team.py` (neu, pytest + TestClient)

1. Ausleihen ohne Team ⇒ `externes_team_id` bleibt `NULL`, kein Tabelleneintrag.
2. Ausleihen mit Team-Name ⇒ Eintrag in `externe_teams`, Ausleihe verknüpft.
3. Zweites Ausleihen mit gleichem Namen ⇒ genau **ein** Tabelleneintrag (kein
   Duplikat), beide Ausleihen verweisen darauf.
4. Team-Name nur aus Whitespace ⇒ wie „für mich" (`NULL`, kein Eintrag).
5. `GET /api/maschinen/externe-teams` ⇒ distinkte, sortierte Namensliste.
6. `AusleiheHistorieOut` enthält `externes_team_name` (gesetzt bzw. `null`).
7. Abwärtskompatibilität: Request ohne `externes_team`-Feld ⇒ für mich, Status 200.

Frontend-Dialog wird manuell verifiziert (Vanilla-JS ohne Test-Harness).

Die gesamte bestehende Suite muss grün bleiben (keine Regression).

## Bewusst nicht im Scope (YAGNI)

- Keine Admin-Verwaltungsseite zum Umbenennen/Löschen von Teams.
- Keine Anzeige des Empfängers in „Meine Ausleihen" oder auf der
  Maschinen-Detailseite (nur Admin-Historie laut Entscheidung).
- Keine Pflicht, externe Teams vorab anzulegen.
