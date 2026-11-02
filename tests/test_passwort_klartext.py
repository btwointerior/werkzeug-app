"""Tests: Klartext-Passwörter werden nirgends mehr gespeichert oder ausgegeben
(Pentest-Befund #1)."""

from backend.models import Rolle
from .conftest import auth_header, make_user


def test_setze_passwort_speichert_keinen_klartext(db):
    u = make_user(db, "max", passwort="geheim123")
    assert not hasattr(u, "passwort_klartext")
    assert u.pruefe_passwort("geheim123") is True


def test_admin_benutzer_liste_enthaelt_keinen_klartext(db, client):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    r = client.get("/api/admin/benutzer", headers=auth_header(admin))
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
    chef = next(b for b in r.json() if b["benutzername"] == "chef")
    assert "passwort_klartext" not in chef


def test_admin_benutzer_anlegen_leakt_kein_klartext(db, client):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    r = client.post(
        "/api/admin/benutzer",
        json={
            "benutzername": "neu",
            "vorname": "Neu",
            "nachname": "Mann",
            "passwort": "pass1234",
        },
        headers=auth_header(admin),
    )
    assert r.status_code == 201
    assert "passwort_klartext" not in r.text
    assert "pass1234" not in r.text


def test_admin_passwort_setzen_leakt_kein_klartext(db, client):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    r = client.put(
        f"/api/admin/benutzer/{user.id}",
        json={"neues_passwort": "reset1234"},
        headers=auth_header(admin),
    )
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
    assert "reset1234" not in r.text


def test_maschinen_endpunkt_leakt_kein_klartext(db, client):
    user = make_user(db, "max", passwort="geheim")
    r = client.get("/api/maschinen", headers=auth_header(user))
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text


def test_me_endpunkt_leakt_kein_klartext(db, client):
    user = make_user(db, "ich", passwort="geheim")
    r = client.get("/api/me", headers=auth_header(user))
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
