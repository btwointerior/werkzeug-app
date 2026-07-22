# Werkzeug-Ausleih-App

Internes System zur Verwaltung und Ausleihe von 200 Handmaschinen für ca. 15 Mitarbeiter.
QR-Code an jeder Maschine -> Scan -> Login -> Maschinen-Profil -> Ausleihen / Zurueckgeben.

## Status

**Phase 1: Datenmodell** - fertig
**Phase 2: Backend & API** - kommt als Naechstes
**Phase 3: Frontend** - geplant
**Phase 4: QR-Codes & Admin-Bereich** - geplant
**Phase 5: Hosting & Inbetriebnahme** - geplant

## Projekt-Struktur

```
werkzeug_app/
├── backend/         Python-Code (FastAPI, Datenmodell)
│   ├── models.py    Tabellen, Beziehungen, Passwort-Logik
│   └── seed.py      Test-Daten anlegen
├── frontend/        HTML, CSS, JS fuer die Handy-Oberflaeche
├── data/            SQLite-Datenbank (werkzeug.db)
├── qr_codes/        generierte QR-Code-PDFs
├── uploads/         Fotos und Betriebsanleitungen
└── requirements.txt
```

## Installation (spaeter auf dem Server / Raspberry Pi)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Datenbank erstellen und Testdaten einfuellen
python -m backend.seed
```

## Das Datenmodell - kurz erklaert

### Tabellen

| Tabelle      | Zweck                                                |
|--------------|------------------------------------------------------|
| `benutzer`   | Mitarbeiter und Admins. Passwoerter werden gehasht.  |
| `maschinen`  | Inventar aller Handmaschinen mit Status              |
| `zubehoer`   | Zubehoerteile pro Maschine (1 Maschine -> N Teile)   |
| `ausleihen`  | Vollstaendige Historie aller Ausleihvorgaenge        |

### Status einer Maschine

- `verfuegbar`   - kann ausgeliehen werden (gruener Button aktiv)
- `ausgeliehen`  - gerade in Benutzung (Ausleihe-Button gesperrt)
- `defekt`       - wurde als kaputt gemeldet, **nur Admin kann freigeben**
- `wartung`      - in Wartung, gesperrt

### Zentrale Logik

- Eine Maschine kann **nur eine offene Ausleihe** gleichzeitig haben.
- Eine Ausleihe gilt als "offen", solange `rueckgabe_zeitpunkt` NULL ist.
- Bei Rueckgabe mit Zustand `defekt` springt die Maschine **automatisch**
  auf Status `defekt` und wird gesperrt.

### Login-Daten (nach Seed)

| Rolle       | Benutzername  | Passwort   |
|-------------|---------------|------------|
| Admin       | `admin`       | `admin123` |
| Mitarbeiter | `max.mueller` | `test1234` |
| Mitarbeiter | `anna.schmidt`| `test1234` |

**Wichtig:** Admin-Passwort beim ersten Login aendern!

## Deploy-Hinweise

- Deploy: `./deploy.sh` (Vorschau) / `./deploy.sh --go` (echter Deploy + Dienst-Neustart).
- `CORS_ORIGINS` in der Server-`.env` muss `capacitor://localhost` enthalten (iOS-App),
  z. B. `CORS_ORIGINS=https://werkzeug.b2interior.de,capacitor://localhost`.
