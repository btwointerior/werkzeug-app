# Design: Pflicht-Zubehör beim Ausleihen (To-Do Punkt 1)

**Datum:** 2026-06-04
**Status:** freigegeben

## Ziel

Beim Ausleihen wird **protokolliert, welches Zubehör tatsächlich mitgenommen**
wurde. Bei der Rückgabe wird diese Liste abgehakt, Fehlendes wird vermerkt. So
bleibt nachvollziehbar, ob mit der Maschine alles wieder zurückkam.

Das bereits vorhandene Zubehör (Tabelle `Zubehoer`, 1 Maschine → N Teile, z. B.
„2 Akkus 18V", „Ladegerät", „Koffer") wird bisher nur informativ auf der
Maschinen-Seite angezeigt. Neu ist das **Mitnahme-Protokoll pro Ausleihe**.

## Kernentscheidungen (aus dem Brainstorming)

- **Goal:** Mitnahme protokollieren (nicht: Pflicht/optional-Kennzeichnung).
- **Erfassung beim Ausleihen:** Checkliste, **nichts vorausgewählt**; Mitarbeiter
  hakt aktiv an, was er mitnimmt.
- **Leere Auswahl:** erlaubt, aber mit Rückfrage „Wirklich ohne Zubehör
  ausleihen?".
- **Rückgabe:** Abhaken + Abgleich; Fehlendes wird im Rückgabe-Protokoll/Kommentar
  vermerkt.

## Datenmodell

Neue Tabelle `ausleihe_zubehoer` (Kind von `Ausleihe`):

| Spalte | Typ | Zweck |
|--------|-----|-------|
| `id` | Integer PK | |
| `ausleihe_id` | FK → `ausleihen.id`, `ondelete=CASCADE` | zu welcher Ausleihe |
| `bezeichnung` | String(120), not null | **Schnappschuss** des Zubehör-Namens zum Ausleih-Zeitpunkt |
| `zurueckgebracht` | Boolean, nullable | `null` = noch offen; `true`/`false` bei Rückgabe gesetzt |

`Ausleihe` bekommt:
```python
mitgenommenes_zubehoer = relationship(
    "AusleiheZubehoer",
    back_populates="ausleihe",
    cascade="all, delete-orphan",
)
```

**Warum Schnappschuss statt FK auf `Zubehoer`:** Der Admin kann die Zubehör-Liste
einer Maschine jederzeit ändern (das Bearbeiten-Formular ersetzt sie komplett,
`cascade delete-orphan` löscht alte Zeilen). Ein FK würde beim nächsten Edit
brechen. Der kopierte Name macht das Protokoll unveränderlich.

**Migration:** Keine Änderung an bestehenden Spalten. `init_db()` nutzt
`Base.metadata.create_all`, das die *fehlende* Tabelle beim nächsten Start
automatisch anlegt — die Produktiv-DB auf Hetzner braucht keinen manuellen
Eingriff. (Verworfen wurde eine JSON-Spalte an `Ausleihe`, weil `create_all`
neue Spalten an *bestehenden* Tabellen nicht ergänzt → manueller `ALTER TABLE`
nötig gewesen wäre.)

## Ablauf Ausleihen

1. Maschine `verfuegbar`, Button `AUSLEIHEN`.
   - Maschine **ohne** Zubehör → wie bisher direkt ausleihen (kein Dialog).
   - Maschine **mit** Zubehör → Zubehör-Dialog öffnet sich.
2. Checkliste aller Zubehörteile, **nichts vorausgewählt**. Mitarbeiter hakt an,
   was er mitnimmt.
3. Bestätigen:
   - ≥1 angehakt → ausleihen, angehakte Teile als Schnappschuss-Zeilen speichern.
   - 0 angehakt → Rückfrage „Wirklich ohne Zubehör ausleihen?" → bei Ja:
     ausleihen, keine Zubehör-Zeilen.

## Ablauf Rückgabe

1. Button `ZURÜCKGEBEN` → bestehender Rückgabe-Dialog (Zustand + Kommentar) wird
   um eine **Abhak-Liste des mitgenommenen Zubehörs** erweitert, alle vorab
   angehakt (Normalfall: alles kommt zurück).
2. Mitarbeiter entfernt Haken bei Fehlendem.
3. Beim Absenden: pro Teil `zurueckgebracht` setzen. Fehlende Teile werden
   **zusätzlich** als Klartext an `rueckgabe_kommentar` angehängt (z. B.
   „⚠ Nicht zurückgegeben: Ladegerät"), damit es in der bestehenden
   Admin-Historie ohne UI-Änderung sichtbar ist.

## API

### Ausleihen — `POST /api/maschinen/{id}/ausleihen`

Neuer optionaler Request-Body:
```json
{ "zubehoer_bezeichnungen": ["2 Akkus 18V", "Ladegerät"] }
```

- Body optional/leer erlaubt (Maschine ohne Zubehör, oder „ohne Zubehör"-Bestätigung).
- Validierung: Jede gesendete `bezeichnung` muss zur aktuellen Zubehör-Liste der
  Maschine passen, sonst **400**. So kann das Frontend nichts Erfundenes speichern.
- Für jede Bezeichnung wird eine `AusleiheZubehoer`-Zeile mit
  `zurueckgebracht=null` angelegt.

### Rückgabe — `POST /api/maschinen/{id}/zurueckgeben`

`ZurueckgabeRequest` erweitert:
```json
{ "zustand": "ok", "kommentar": "...",
  "zurueckgebrachte_zubehoer_ids": [12, 13] }
```

- Liste der `AusleiheZubehoer.id`, die zurückkamen.
- Backend setzt `zurueckgebracht=true` für genannte IDs, `false` für die übrigen
  der Ausleihe.
- Fehlende (`false`) werden zu einer Zeile zusammengefasst und an `kommentar`
  angehängt.
- **Abwärtskompatibel:** fehlt das Feld (`None`), gilt alles als zurückgebracht
  (kein Bruch bestehender Aufrufe).

## Schemas (`schemas.py`)

- `AusleiheZubehoerOut` (`id`, `bezeichnung`, `zurueckgebracht`) — eingebettet in
  `AusleiheKurz` / `MeineAusleiheOut`, damit das Frontend bei der Rückgabe die
  mitgenommene Liste samt IDs kennt.
- `AusleihenRequest` (`zubehoer_bezeichnungen: list[str] = []`).
- `ZurueckgabeRequest` um `zurueckgebrachte_zubehoer_ids: Optional[list[int]] = None`.

## Geänderte Dateien

- `backend/models.py` — neue Tabelle `AusleiheZubehoer` + Relationship.
- `backend/schemas.py` — neue/erweiterte Schemas.
- `backend/routers/maschinen_router.py` — beide Endpunkte erweitern.
- `frontend/js/views/maschine.js` — Ausleih-Dialog + Rückgabe-Dialog erweitern.
- `frontend/js/api.js` — Body-Übergabe (POST hat bereits Body-Support).

## Tests

Neue Datei `tests/test_zubehoer_protokoll.py` auf bestehender
`pytest` + `TestClient`-Infrastruktur (temporäre SQLite-Test-DB).

**Ausleihen:**
1. Ausleihen mit Teil-Auswahl → 200, genau die angehakten `AusleiheZubehoer`-Zeilen
   existieren mit `zurueckgebracht=null`.
2. Ausleihen mit leerer Liste → 200, keine Zubehör-Zeilen (Maschine trotzdem
   `ausgeliehen`).
3. Ausleihen mit unbekannter Bezeichnung → 400, keine Ausleihe angelegt.
4. Schnappschuss: nach Ausleihe Zubehör der Maschine umbenennen/löschen →
   Protokoll-Zeile bleibt unverändert.

**Rückgabe:**
5. Rückgabe, alle Teile zurück → alle `zurueckgebracht=true`, Kommentar ohne
   Fehl-Vermerk.
6. Rückgabe mit fehlendem Teil → genanntes `true`, Rest `false`,
   „⚠ Nicht zurückgegeben: …" im `rueckgabe_kommentar`.
7. Rückgabe ohne das neue Feld → alles gilt als zurückgebracht, kein Fehler.

**Anzeige:**
8. `GET /api/maschinen/meine` liefert die mitgenommene Zubehör-Liste mit `id` +
   `zurueckgebracht`.

Vorgehen: jeder Test zuerst rot, dann Implementierung bis grün (red-green-refactor).

## Nicht im Scope

- Pflicht/optional-Kennzeichnung einzelner Zubehörteile (bewusst verworfen).
- Mengen-Erfassung (z. B. „1 von 2 Akkus") — nur Teil vorhanden/fehlt.
- Admin-Auswertung/Statistik über fehlendes Zubehör (kann später folgen).
