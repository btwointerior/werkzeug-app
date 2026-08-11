# Passwort selbst ändern + Haupt-Admin-Schutz

Datum: 2026-08-11 · Status: vom User freigegeben („passt")

## Ziel

1. Jeder eingeloggte Benutzer kann sein eigenes Passwort ändern.
2. Nach der Selbst-Änderung sieht der Admin das Passwort **nicht** mehr im Klartext,
   kann es aber weiterhin zurücksetzen (neues Passwort setzen → Klartext wieder sichtbar).
3. Nur der Benutzer `admin` (Haupt-Admin, erkannt am Benutzernamen) darf Profile mit
   Admin-Rolle bearbeiten/löschen und die Admin-Rolle vergeben.

## Backend

### Eigenes Passwort ändern

- **`POST /api/passwort-aendern`** (auth_router, jeder eingeloggte Benutzer).
  Body: `{ aktuelles_passwort: str, neues_passwort: str (min. 4 Zeichen) }`.
- Ablauf: Brute-Force-Drossel prüfen (Key `ip:benutzername`, gleiche Mechanik wie Login)
  → aktuelles Passwort verifizieren (falsch → 400 + Fehlversuch merken)
  → `setze_passwort(neu, merke_klartext=False)` → Commit → 200 mit Bestätigung.
- **`Benutzer.setze_passwort(klartext, merke_klartext=True)`** bekommt den neuen
  Parameter: bei `False` wird der Hash gesetzt und `passwort_klartext = None` gelöscht.
  Admin-Wege (Anlegen, Reset via `neues_passwort`) bleiben bei `True` → Klartext
  wieder sichtbar. Keine DB-Migration nötig (`passwort_klartext` ist nullable).

### Haupt-Admin-Regeln (admin_router)

Konstante `HAUPT_ADMIN = "admin"`. Für alle drei Benutzer-Endpunkte gilt:

- `PUT /api/admin/benutzer/{id}`: Ziel hat Admin-Rolle **oder** Update setzt
  `rolle=admin` → nur Haupt-Admin, sonst 403.
- `DELETE /api/admin/benutzer/{id}`: Ziel hat Admin-Rolle → nur Haupt-Admin, sonst 403.
- `POST /api/admin/benutzer`: `rolle=admin` → nur Haupt-Admin, sonst 403
  (sonst wäre die Regel per frischem Admin-Konto umgehbar).
- Lockout-Schutz: das Konto `admin` kann **nie** gesperrt (`aktiv=false`) oder
  herabgestuft (`rolle=mitarbeiter`) werden → 400, auch nicht durch sich selbst.
  Löschen von `admin` ist damit unmöglich (Admin-Ziel ⇒ nur Haupt-Admin ⇒
  Selbst-Löschen ist bereits verboten).

## Frontend

- **Topbar**: 🔑-Button neben „Abmelden" (alle Benutzer, Web + iOS-App) → Modal mit
  drei Feldern: aktuelles Passwort, neues Passwort, neues Passwort wiederholen.
  Client-Validierung (min. 4 Zeichen, Wiederholung gleich), Erfolg/Fehler als Toast.
- **Admin-Benutzerliste** (`admin_benutzer.js`):
  - `passwort_klartext == null` → kursiv „— vom Benutzer geändert" statt Punkte+anzeigen.
  - Ist der eingeloggte Benutzer nicht `admin`: „Bearbeiten"-Button bei
    Admin-Profilen ausgeblendet, Rollen-Auswahl „Admin" deaktiviert.
  - Beim Konto `admin` selbst: Rolle + Aktiv-Häkchen deaktiviert (Server erzwingt es ohnehin).

## Tests

- pytest (neu `tests/test_passwort_aendern.py`, `tests/test_haupt_admin_schutz.py`):
  Erfolgsfall (neues PW gilt, altes nicht, Klartext = None, Admin-Liste ohne Klartext),
  falsches aktuelles PW (400, unverändert), zu kurz (422), ohne Login (401),
  Drossel (429), Admin-Reset stellt Klartext wieder her; alle Haupt-Admin-Regeln
  positiv (als `admin`) und negativ (als zweiter Admin) + Lockout-Schutz.
- Puppeteer-E2E lokal: Mitarbeiter ändert Passwort über das Overlay → Re-Login mit
  neuem Passwort; Admin-Liste zeigt „vom Benutzer geändert".

## Deploy

Web: `git push` + `./deploy.sh --go` (keine Migration). iOS: TestFlight-Build
`app-v1.2.5` (Frontend wird beim Codemagic-Build gebündelt).
