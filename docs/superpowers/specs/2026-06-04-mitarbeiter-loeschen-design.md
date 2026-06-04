# Design: Mitarbeiter löschen (To-Do Punkt 2)

**Datum:** 2026-06-04
**Status:** freigegeben

## Ziel

Ein Admin kann einen Mitarbeiter **echt löschen** (aus der Datenbank entfernen) –
aber nur, wenn dadurch keine Ausleih-Historie zerstört wird. Das bereits
vorhandene „Sperren/Deaktivieren“ (`aktiv = false`) bleibt unverändert daneben
bestehen.

## Kernregel

Echtes Löschen ist **nur erlaubt, wenn der Mitarbeiter keine einzige Ausleihe
hat** (weder offen noch in der Historie). Hat er Ausleihen, wird das Löschen
abgelehnt mit dem Hinweis, ihn stattdessen zu sperren. So bleibt die Audit-Spur
lückenlos. (Eine offene Ausleihe ist ebenfalls ein Historien-Eintrag und wird
damit automatisch mit-geblockt.)

## Backend

Neuer Endpunkt im bestehenden Admin-Router (`backend/routers/admin_router.py`):

```
DELETE /api/admin/benutzer/{benutzer_id}   -> 204 No Content
```

Nur für Admins (gleiches Auth-Muster wie die übrigen Admin-Routen). Prüfungen
der Reihe nach:

| # | Prüfung | HTTP | Meldung |
|---|---------|------|---------|
| 1 | Benutzer existiert nicht | 404 | „Benutzer nicht gefunden.“ |
| 2 | Benutzer == eingeloggter Admin (Selbst-Löschen) | 400 | „Sie können sich nicht selbst löschen.“ |
| 3 | Benutzer ist der letzte aktive Admin | 400 | „Der letzte Admin kann nicht gelöscht werden.“ |
| 4 | Benutzer hat ≥ 1 Ausleihe | 409 | „Mitarbeiter hat Ausleih-Historie und kann nicht gelöscht werden. Bitte stattdessen sperren.“ |
| 5 | sonst | 204 | (löschen + commit) |

## Frontend

`frontend/js/views/admin_benutzer.js`: im Bearbeiten-Dialog ein roter Button
**„Mitarbeiter löschen“** mit Sicherheitsabfrage („… wirklich löschen?“).
- Bei Erfolg: Dialog schließen, Liste neu laden.
- Bei `409`: die „bitte sperren“-Meldung anzeigen (Sperren-Häkchen ist vorhanden).
- Beim eigenen Konto: Button ausgeblendet.

## Tests

Projekt hat bisher keine Tests. Mit diesem Feature wird `pytest` + FastAPI
`TestClient` (eigene temporäre SQLite-Test-DB, kein Zugriff auf die echte DB)
eingeführt. Abgedeckte Fälle:

1. Löschen eines Mitarbeiters ohne Ausleihen → 204, Benutzer ist weg.
2. Selbst-Löschen → 400.
3. Letzter Admin → 400.
4. Mitarbeiter mit Ausleihe → 409, Benutzer bleibt erhalten.
5. Nicht vorhandener Benutzer → 404.
6. Nicht-Admin ruft Endpoint → 403 (vorhandenes Auth-Verhalten).

## Nicht im Scope

- Änderungen am bestehenden Sperren/Deaktivieren.
- Anonymisieren oder Mitlöschen von Historie (bewusst verworfen).
