"""Tests: nur der Haupt-Admin (Benutzername "admin") darf Admin-Profile verwalten."""

from backend.models import Rolle

from .conftest import auth_header, make_user


def _setup(db):
    haupt = make_user(db, "admin", rolle=Rolle.ADMIN, passwort="admin1234")
    zweit = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="chef1234")
    normal = make_user(db, "max", passwort="max12345")
    return haupt, zweit, normal


# ---- Bearbeiten (PUT) ----

def test_zweitadmin_darf_adminprofil_nicht_bearbeiten(db, client):
    haupt, zweit, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{haupt.id}",
        json={"vorname": "Neu"},
        headers=auth_header(zweit),
    )
    assert r.status_code == 403


def test_zweitadmin_darf_adminpasswort_nicht_zuruecksetzen(db, client):
    haupt, zweit, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{haupt.id}",
        json={"neues_passwort": "gekapert1"},
        headers=auth_header(zweit),
    )
    assert r.status_code == 403


def test_hauptadmin_darf_adminprofil_bearbeiten(db, client):
    haupt, zweit, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{zweit.id}",
        json={"vorname": "Neu"},
        headers=auth_header(haupt),
    )
    assert r.status_code == 200
    assert r.json()["vorname"] == "Neu"


def test_zweitadmin_darf_mitarbeiter_weiter_bearbeiten(db, client):
    _, zweit, normal = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{normal.id}",
        json={"vorname": "Neu"},
        headers=auth_header(zweit),
    )
    assert r.status_code == 200


# ---- Rollen-Vergabe ----

def test_zweitadmin_darf_nicht_zum_admin_hochstufen(db, client):
    _, zweit, normal = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{normal.id}",
        json={"rolle": "admin"},
        headers=auth_header(zweit),
    )
    assert r.status_code == 403


def test_hauptadmin_darf_hochstufen(db, client):
    haupt, _, normal = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{normal.id}",
        json={"rolle": "admin"},
        headers=auth_header(haupt),
    )
    assert r.status_code == 200
    assert r.json()["rolle"] == "admin"


def test_zweitadmin_darf_keinen_admin_anlegen(db, client):
    _, zweit, _ = _setup(db)
    r = client.post(
        "/api/admin/benutzer",
        json={
            "benutzername": "neuadmin",
            "vorname": "Neu",
            "nachname": "Admin",
            "passwort": "pass1234",
            "rolle": "admin",
        },
        headers=auth_header(zweit),
    )
    assert r.status_code == 403


def test_zweitadmin_darf_mitarbeiter_anlegen(db, client):
    _, zweit, _ = _setup(db)
    r = client.post(
        "/api/admin/benutzer",
        json={
            "benutzername": "neuer",
            "vorname": "Neu",
            "nachname": "Mann",
            "passwort": "pass1234",
        },
        headers=auth_header(zweit),
    )
    assert r.status_code == 201


def test_hauptadmin_darf_admin_anlegen(db, client):
    haupt, _, _ = _setup(db)
    r = client.post(
        "/api/admin/benutzer",
        json={
            "benutzername": "neuadmin",
            "vorname": "Neu",
            "nachname": "Admin",
            "passwort": "pass1234",
            "rolle": "admin",
        },
        headers=auth_header(haupt),
    )
    assert r.status_code == 201
    assert r.json()["rolle"] == "admin"


# ---- Löschen (DELETE) ----

def test_zweitadmin_darf_adminprofil_nicht_loeschen(db, client):
    haupt, zweit, _ = _setup(db)
    r = client.delete(
        f"/api/admin/benutzer/{haupt.id}", headers=auth_header(zweit)
    )
    assert r.status_code == 403


def test_hauptadmin_darf_zweitadmin_loeschen(db, client):
    haupt, zweit, _ = _setup(db)
    r = client.delete(
        f"/api/admin/benutzer/{zweit.id}", headers=auth_header(haupt)
    )
    assert r.status_code == 204


def test_zweitadmin_darf_mitarbeiter_weiter_loeschen(db, client):
    _, zweit, normal = _setup(db)
    r = client.delete(
        f"/api/admin/benutzer/{normal.id}", headers=auth_header(zweit)
    )
    assert r.status_code == 204


# ---- Lockout-Schutz für das Konto "admin" ----

def test_admin_konto_kann_nicht_gesperrt_werden(db, client):
    haupt, _, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{haupt.id}",
        json={"aktiv": False},
        headers=auth_header(haupt),
    )
    assert r.status_code == 400


def test_admin_konto_kann_nicht_herabgestuft_werden(db, client):
    haupt, _, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{haupt.id}",
        json={"rolle": "mitarbeiter"},
        headers=auth_header(haupt),
    )
    assert r.status_code == 400


def test_hauptadmin_darf_eigenes_konto_sonst_bearbeiten(db, client):
    haupt, _, _ = _setup(db)
    r = client.put(
        f"/api/admin/benutzer/{haupt.id}",
        json={"vorname": "Fredy"},
        headers=auth_header(haupt),
    )
    assert r.status_code == 200
