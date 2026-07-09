"""Regressionstests für die Härtungs-/Bugfix-Runde (fix/bugfix-haertung)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import Ausleihe, AusleiheZubehoer, Maschine, MaschinenStatus
from tests.conftest import auth_header, make_user


# --- Bug 1: nur EINE offene Ausleihe pro Maschine (Doppel-Ausleihe-Race) ---

def test_offene_ausleihe_pro_maschine_nur_einmal(db):
    """Zwei gleichzeitig offene Ausleihen für dieselbe Maschine müssen die DB
    per partiellem Unique-Index ablehnen (Absicherung gegen die Race Condition)."""
    m = Maschine(maschinen_code="M-0001", name="Bohrer", status=MaschinenStatus.VERFUEGBAR)
    u = make_user(db, "u1")
    db.add(m)
    db.commit()
    db.refresh(m)

    db.add(Ausleihe(maschine_id=m.id, benutzer_id=u.id))
    db.commit()

    db.add(Ausleihe(maschine_id=m.id, benutzer_id=u.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_zweite_ausleihe_nach_rueckgabe_erlaubt(db):
    """Nach Rückgabe (rueckgabe_zeitpunkt gesetzt) darf dieselbe Maschine erneut
    ausgeliehen werden — der partielle Index deckt nur offene Ausleihen ab."""
    m = Maschine(maschinen_code="M-0002", name="Säge", status=MaschinenStatus.VERFUEGBAR)
    u = make_user(db, "u2")
    db.add(m)
    db.commit()
    db.refresh(m)

    erste = Ausleihe(
        maschine_id=m.id,
        benutzer_id=u.id,
        rueckgabe_zeitpunkt=datetime.now(timezone.utc),
    )
    db.add(erste)
    db.commit()

    db.add(Ausleihe(maschine_id=m.id, benutzer_id=u.id))
    db.commit()  # darf NICHT werfen


def test_ausleihen_race_gibt_konflikt_statt_500(client, db):
    """Simuliert das Race-Fenster: Maschine steht noch auf VERFUEGBAR, aber es
    existiert bereits eine offene Ausleihe (der andere Request war schneller).
    Der Commit läuft in den Unique-Index -> sauberer 409 statt 500."""
    m = Maschine(maschinen_code="M-0009", name="Flex", status=MaschinenStatus.VERFUEGBAR)
    erster = make_user(db, "erster")
    zweiter = make_user(db, "zweiter")
    db.add(m)
    db.commit()
    db.refresh(m)
    db.add(Ausleihe(maschine_id=m.id, benutzer_id=erster.id))
    db.commit()

    resp = client.post(f"/api/maschinen/{m.id}/ausleihen", headers=auth_header(zweiter))
    assert resp.status_code == 409, resp.text
    assert "ausgeliehen" in resp.json()["detail"].lower()


# --- Bug 2: dauer_tage darf bei aware-Zeitstempeln nicht crashen ---

def test_dauer_tage_kein_crash_bei_aware_zeitstempel():
    """Property mischt sonst naive/aware datetimes -> TypeError."""
    a = Ausleihe(
        maschine_id=1,
        benutzer_id=1,
        ausleih_zeitpunkt=datetime.now(timezone.utc) - timedelta(days=3, hours=1),
    )
    assert a.dauer_tage == 3


# --- Bug 3: Foreign Keys werden bei SQLite tatsächlich erzwungen ---

def test_foreign_keys_werden_erzwungen(db):
    """Ohne PRAGMA foreign_keys=ON greifen die ondelete-Regeln nicht.
    Eine Ausleihe mit nicht existierender Maschine muss abgelehnt werden."""
    db.add(Ausleihe(maschine_id=9999, benutzer_id=9999))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_maschine_mit_historie_loeschbar_trotz_fk_enforcement(db):
    """Bei aktivem PRAGMA foreign_keys=ON muss das Löschen einer Maschine mit
    abgeschlossener Ausleih-Historie via ORM-Kaskade klappen (kein FK-Fehler)."""
    m = Maschine(maschinen_code="M-0100", name="Hobel", status=MaschinenStatus.VERFUEGBAR)
    u = make_user(db, "hist")
    db.add(m)
    db.commit()
    db.refresh(m)
    a = Ausleihe(
        maschine_id=m.id,
        benutzer_id=u.id,
        rueckgabe_zeitpunkt=datetime.now(timezone.utc),
    )
    a.mitgenommenes_zubehoer.append(AusleiheZubehoer(bezeichnung="Akku"))
    db.add(a)
    db.commit()

    db.delete(m)
    db.commit()  # darf NICHT werfen

    assert db.query(Ausleihe).count() == 0
    assert db.query(AusleiheZubehoer).count() == 0


# --- Bug 4: Brute-Force-Schutz am Login ---

def test_login_drosselt_nach_zu_vielen_fehlversuchen(client, db):
    make_user(db, "opfer", passwort="richtig")
    for _ in range(5):
        r = client.post("/api/login", json={"benutzername": "opfer", "passwort": "falsch"})
        assert r.status_code == 401
    r = client.post("/api/login", json={"benutzername": "opfer", "passwort": "falsch"})
    assert r.status_code == 429


def test_erfolgreicher_login_setzt_drossel_zurueck(client, db):
    make_user(db, "gut", passwort="richtig")
    for _ in range(3):
        client.post("/api/login", json={"benutzername": "gut", "passwort": "falsch"})
    ok = client.post("/api/login", json={"benutzername": "gut", "passwort": "richtig"})
    assert ok.status_code == 200
    # Zähler zurückgesetzt -> weitere Fehlversuche starten wieder bei 0
    for _ in range(4):
        r = client.post("/api/login", json={"benutzername": "gut", "passwort": "falsch"})
        assert r.status_code == 401


# --- Bug 5: Token-Sliding nur bei bald ablaufendem Token, nur auf API-Pfaden ---

def test_frischer_token_wird_nicht_erneuert(client, db):
    u = make_user(db, "frisch")
    r = client.get("/api/me", headers=auth_header(u))
    assert r.status_code == 200
    assert "X-New-Token" not in r.headers


def test_bald_ablaufender_token_wird_erneuert(client, db):
    from jose import jwt
    from backend.config import settings

    u = make_user(db, "bald")
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = jwt.encode(
        {"sub": str(u.id), "exp": exp}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    r = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "X-New-Token" in r.headers


# --- Bug 6: CORS spiegelt nicht mehr jeden Origin ---

def test_cors_erlaubt_keinen_fremden_origin(client, db):
    u = make_user(db, "cors")
    r = client.get(
        "/api/me",
        headers={**auth_header(u), "Origin": "http://evil.example"},
    )
    assert r.headers.get("access-control-allow-origin") != "*"
    assert r.headers.get("access-control-allow-origin") != "http://evil.example"


# --- Bug 7: Security-Header ---

def test_security_header_gesetzt(client):
    r = client.get("/api/maschinen")  # 401 ist ok, Header sollen trotzdem da sein
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers
