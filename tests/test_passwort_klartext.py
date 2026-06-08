"""Tests für die Klartext-Passwort-Speicherung & Admin-Anzeige."""

from backend.models import Rolle
from .conftest import auth_header, make_user


def test_setze_passwort_speichert_klartext(db):
    u = make_user(db, "max", passwort="geheim123")
    assert u.passwort_klartext == "geheim123"
    assert u.pruefe_passwort("geheim123") is True


def test_admin_benutzer_liefert_klartext(db, client):
    admin = make_user(db, "chef", rolle=Rolle.ADMIN, passwort="adminpw")
    r = client.get("/api/admin/benutzer", headers=auth_header(admin))
    assert r.status_code == 200
    chef = next(b for b in r.json() if b["benutzername"] == "chef")
    assert chef["passwort_klartext"] == "adminpw"


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
