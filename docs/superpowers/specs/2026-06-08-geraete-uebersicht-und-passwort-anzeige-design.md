# Design: Geräte-Übersicht (Suche & Filter) + Klartext-Passwort-Anzeige für Admin

**Datum:** 2026-06-08
**Status:** Entwurf zur Review

## Überblick

Zwei Funktionen werden ergänzt:

1. **Geräte-Übersicht** — eine neue Ansicht, in der **alle eingeloggten Nutzer** (nicht nur
   Admins) sämtliche Maschinen sehen, per Freitext durchsuchen und nach Status filtern können.
   Die bestehende Admin-Maschinenliste wird auf dieselbe (geteilte) Filterlogik umgestellt.
2. **Klartext-Passwort-Anzeige** — der Admin kann in der Benutzerverwaltung das Passwort eines
   Nutzers im Klartext sehen.

---

## Teil 1 — Geräte-Übersicht mit Suche & Filter

### Ausgangslage

- **Admin** hat bereits `GET /api/admin/maschinen` und eine Listenansicht
  (`admin_maschinen.js`) mit Freitext-Suche (client-seitig) + Status-Dropdown.
- **Normaler Nutzer** hat nur „Meine Ausleihen", Einzel-Lookup per Code und QR-Scan —
  **keinen** Überblick über alle Geräte.

### Backend

- Neuer Endpunkt `GET /api/maschinen` in `backend/routers/maschinen_router.py`:
  - Auth: `get_current_user` (jede Rolle, nicht nur Admin).
  - Antwort: `list[MaschineOut]`, sortiert nach `maschinen_code`.
  - Baut die Ausgabe über `maschine_zu_out(m, current_user.id)` (Foto-/Anleitungs-URLs
    inkl. Datei-Token) — analog zum Admin-Endpunkt.
  - Liefert die **komplette** Liste; Filtern passiert client-seitig.
- **Keine** Modell- oder Schema-Änderung (bestehendes `MaschineOut` wird wiederverwendet).

### Frontend

- **Gemeinsames Filter-Modul** `frontend/js/filter.js`:
  - Reine Funktion `filterMaschinen(liste, { suche, status })` → gefiltertes Array.
  - Freitext (case-insensitive, getrimmt) über **Name, Code, Hersteller, Platznummer,
    Seriennummer**. Leeres/fehlendes Feld wird übersprungen (kein Treffer-Ausschluss).
  - `status`: exakter Vergleich; leer/`""` = alle Status.
  - Rein und ohne DOM-Abhängigkeit → unit-testbar (wie `parseScan`).
- **Neue View** `frontend/js/views/geraete.js`:
  - Überschrift „Geräte".
  - Filterleiste: Suchfeld + Status-Dropdown (gleiche UI-Bausteine wie `admin_maschinen.js`).
  - Karten-Liste im Stil von `meine.js`: Name, Code, `statusBadge`; jede Karte verlinkt auf
    `#/m/CODE` (bestehende Maschinen-Ansicht).
  - Lädt einmal `GET /api/maschinen`, hält die Liste im Speicher; bei jeder Eingabe wird
    `filterMaschinen` neu angewendet und neu gerendert (keine Server-Roundtrips beim Tippen).
  - Leerzustand über `leerZustand`, Ladezustand über `spinner`, Fehlerbehandlung wie in
    `meine.js`.
- **Routing** (`frontend/js/app.js`):
  - Neue Route `{ pattern: /^#\/geraete$/, view: renderGeraete }` (eingeloggt, kein
    `admin: true`).
  - Bottom-Nav: neuer Eintrag „Geräte" (Icon 🔧) für alle eingeloggten Nutzer, eingeordnet
    vor „Meine".
- **Admin-Verbesserung** (`frontend/js/views/admin_maschinen.js`):
  - Bestehende Inline-Filterlogik durch `filterMaschinen` aus dem geteilten Modul ersetzen.
  - Dadurch durchsucht auch die Admin-Suche zusätzlich Hersteller & Platznummer (heute nur
    Name/Code/Serie) — gewünschte Verbesserung, keine Funktionsregression.

### Datenfluss

```
renderGeraete() → GET /api/maschinen → alleMaschinen (im Speicher)
   ↓ (bei jeder Sucheingabe / Status-Auswahl)
filterMaschinen(alleMaschinen, { suche, status }) → render(karten)
   ↓ (Klick auf Karte)
location.hash = #/m/CODE → bestehende Maschinen-Ansicht
```

### Tests

- `tests/js/filter.test.mjs` (Node `--test`, wie `parse_scan.test.mjs`):
  - Freitext findet über Name, Code, Hersteller, Platznummer, Seriennummer.
  - Case-insensitiv und getrimmt.
  - Status-Filter exakt; leerer Status = alle.
  - Kombination Suche + Status.
  - Leere Eingabe = ungefilterte Liste.
- Backend-Test (pytest) für `GET /api/maschinen`:
  - Normaler (Nicht-Admin-)Nutzer erhält die Liste (200) inkl. aller Status.
  - Nicht eingeloggt → 401.

---

## Teil 2 — Klartext-Passwort-Anzeige für Admin

> **Sicherheitshinweis (im Code dokumentieren):** Auf ausdrücklichen, informierten Wunsch des
> Betreibers werden Passwörter zusätzlich im Klartext gespeichert, damit der Admin sie ansehen
> kann. Das ist bewusst gegen die übliche Sicherheitsempfehlung. Bei einem DB-/Backup-Leak
> liegen alle so gespeicherten Passwörter offen. **Bestehende Passwörter bleiben unsichtbar**,
> bis sie nach der Umstellung neu gesetzt werden (Einweg-Hash ist nicht rückrechenbar).

### Backend

- **Modell** `Benutzer` (`backend/models.py`):
  - Neue Spalte `passwort_klartext = Column(String(255), nullable=True)`.
  - `setze_passwort(klartext)` speichert zusätzlich `self.passwort_klartext = klartext`
    (Hash bleibt für die Anmeldung maßgeblich).
  - Kommentar an der Methode, der den Sicherheitskompromiss erklärt.
- **Schema** `BenutzerOut` (`backend/schemas.py`):
  - Neues Feld `passwort_klartext: Optional[str] = None`.
  - Wird nur über Admin-Endpunkte ausgeliefert (`/api/admin/...`), nie über Nutzer-Endpunkte.
- **Endpunkt**: `GET /api/admin/benutzer` liefert das Feld automatisch über `BenutzerOut` mit.
  Kein neuer Endpunkt nötig.

### Frontend

- `frontend/js/views/admin_benutzer.js`:
  - Pro Benutzer das Klartext-Passwort anzeigen.
  - Standardmäßig maskiert (`••••••••`) mit Augen-Toggle zum Ein-/Ausblenden, um
    Schulter-Mitlesen zu reduzieren.
  - Wenn `passwort_klartext` leer ist (Altbestand vor Umstellung): Hinweis „— (vor Umstellung
    gesetzt)" anzeigen.

### Migration / Deployment

- `create_all` legt **keine** Spalten in bestehenden Tabellen an (siehe
  Deploy-Migrations-Notiz). Nach dem Deploy auf Hetzner ist die Spalte manuell nachzuziehen:
  ```sql
  ALTER TABLE benutzer ADD COLUMN passwort_klartext VARCHAR(255);
  ```
- Lokal (frische DB) entsteht die Spalte über `create_all` automatisch.

### Tests

- pytest:
  - Nach `setze_passwort("geheim")` ist `passwort_klartext == "geheim"` und
    `pruefe_passwort("geheim")` ist `True`.
  - `GET /api/admin/benutzer` enthält `passwort_klartext` für neu angelegte Nutzer.
  - Nutzer-Endpunkte geben `passwort_klartext` **nicht** preis (z. B. `/api/maschinen/meine`
    oder ein Profil-Endpunkt, falls vorhanden — sonst nur prüfen, dass das Feld nicht im
    MaschineOut/Mitarbeiter-Pfad auftaucht).

---

## Bewusst nicht enthalten (YAGNI)

- Server-seitige Filterung mit Query-Parametern für die Geräte-Übersicht (Bestand ist klein;
  client-seitig reicht).
- Hersteller-/Platznummer-Dropdown-Filter (nur Freitext + Status gewünscht).
- Passwort-Reset-Workflow / Pflicht-Wechsel beim Login.
- Pagination der Geräteliste.
