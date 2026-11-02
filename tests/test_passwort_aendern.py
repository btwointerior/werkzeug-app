"""Tests: eigenes Passwort ändern (POST /api/passwort-aendern)."""

from backend.models import Rolle

from .conftest import auth_header, make_user


def _aendern(client, user, aktuell, neu):
    return client.post(
        "/api/passwort-aendern",
        json={"aktuelles_passwort": aktuell, "neues_passwort": neu},
        headers=auth_header(user),
    )


def test_erfolgreiche_aenderung(client, db):
    user = make_user(db, "max", passwort="alt12345")
    r = _aendern(client, user, "alt12345", "neu12345")
    assert r.status_code == 200

    db.refresh(user)
    assert user.pruefe_passwort("neu12345") is True
    assert user.pruefe_passwort("alt12345") is False


def test_aenderung_leakt_kein_klartext(client, db):
    user = make_user(db, "max", passwort="alt12345")
    r = _aendern(client, user, "alt12345", "neu12345")
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
    assert "neu12345" not in r.text


def test_admin_liste_zeigt_keinen_klartext_nach_aenderung(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    _aendern(client, user, "alt12345", "neu12345")

    r = client.get("/api/admin/benutzer", headers=auth_header(admin))
    max_eintrag = next(b for b in r.json() if b["benutzername"] == "max")
    assert "passwort_klartext" not in max_eintrag


def test_admin_reset_setzt_neues_passwort_funktionsfaehig(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN, passwort="adminpw")
    user = make_user(db, "max", passwort="alt12345")
    _aendern(client, user, "alt12345", "neu12345")

    r = client.put(
        f"/api/admin/benutzer/{user.id}",
        json={"neues_passwort": "reset1234"},
        headers=auth_header(admin),
    )
    assert r.status_code == 200
    assert "passwort_klartext" not in r.text
    assert "reset1234" not in r.text

    db.refresh(user)
    assert user.pruefe_passwort("reset1234") is True
    assert user.pruefe_passwort("neu12345") is False


def test_falsches_aktuelles_passwort(client, db):
    user = make_user(db, "max", passwort="alt12345")
    r = _aendern(client, user, "falschfalsch", "neu12345")
    assert r.status_code == 400

    db.refresh(user)
    assert user.pruefe_passwort("alt12345") is True


def test_neues_passwort_zu_kurz(client, db):
    user = make_user(db, "max", passwort="alt12345")
    r = _aendern(client, user, "alt12345", "abc")
    assert r.status_code == 422


def test_ohne_login_401(client, db):
    r = client.post(
        "/api/passwort-aendern",
        json={"aktuelles_passwort": "x", "neues_passwort": "neu12345"},
    )
    assert r.status_code == 401


def test_drossel_nach_fehlversuchen(client, db):
    user = make_user(db, "max", passwort="alt12345")
    for _ in range(5):
        r = _aendern(client, user, "falschfalsch", "neu12345")
        assert r.status_code == 400
    r = _aendern(client, user, "alt12345", "neu12345")
    assert r.status_code == 429
