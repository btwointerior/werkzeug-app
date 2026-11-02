"""Tests: POST /api/admin/benutzer/{id}/neues-passwort (Pentest-Befund #1).

Erzeugt ein zufälliges Passwort, speichert nur den Hash und liefert das
Passwort GENAU EINMAL in der Antwort zurück."""

from backend.models import Rolle

from .conftest import auth_header, make_user


def _reset(client, admin, benutzer_id):
    return client.post(
        f"/api/admin/benutzer/{benutzer_id}/neues-passwort",
        headers=auth_header(admin),
    )


def test_nur_admin_darf_zuruecksetzen(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    mitarbeiter = make_user(db, "max", passwort="max12345")
    r = client.post(
        f"/api/admin/benutzer/{admin.id}/neues-passwort",
        headers=auth_header(mitarbeiter),
    )
    assert r.status_code == 403


def test_antwort_enthaelt_passwort(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    r = _reset(client, admin, user.id)
    assert r.status_code == 200
    daten = r.json()
    assert "passwort" in daten
    assert isinstance(daten["passwort"], str)
    assert len(daten["passwort"]) == 12


def test_zweiter_aufruf_liefert_anderes_passwort(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    pw1 = _reset(client, admin, user.id).json()["passwort"]
    pw2 = _reset(client, admin, user.id).json()["passwort"]
    assert pw1 != pw2


def test_login_mit_neuem_passwort_funktioniert_altes_nicht_mehr(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    neues_passwort = _reset(client, admin, user.id).json()["passwort"]

    r_alt = client.post(
        "/api/login", json={"benutzername": "max", "passwort": "alt12345"}
    )
    assert r_alt.status_code == 401

    r_neu = client.post(
        "/api/login", json={"benutzername": "max", "passwort": neues_passwort}
    )
    assert r_neu.status_code == 200


def test_unbekannter_benutzer_404(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    r = _reset(client, admin, 999999)
    assert r.status_code == 404


def test_passwort_zeichensatz_ohne_verwechselbare_zeichen(client, db):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    for _ in range(20):
        pw = _reset(client, admin, user.id).json()["passwort"]
        assert not any(c in pw for c in "lIO0")
