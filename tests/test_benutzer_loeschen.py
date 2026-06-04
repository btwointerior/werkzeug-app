"""Tests für DELETE /api/admin/benutzer/{id} (To-Do Punkt 2)."""

from datetime import datetime, timezone

from backend.models import Ausleihe, Benutzer, Maschine, MaschinenStatus, Rolle

from .conftest import auth_header, make_user


def test_loescht_mitarbeiter_ohne_ausleihen(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN)
    ziel = make_user(db, "max")

    r = client.delete(f"/api/admin/benutzer/{ziel.id}", headers=auth_header(admin))

    assert r.status_code == 204
    assert db.query(Benutzer).filter(Benutzer.id == ziel.id).first() is None


def test_selbst_loeschen_verboten(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN)

    r = client.delete(f"/api/admin/benutzer/{admin.id}", headers=auth_header(admin))

    assert r.status_code == 400
    assert db.query(Benutzer).filter(Benutzer.id == admin.id).first() is not None


def test_mitarbeiter_mit_ausleihe_nicht_loeschbar(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN)
    ziel = make_user(db, "max")
    maschine = Maschine(
        maschinen_code="M-0001",
        name="Bohrmaschine",
        status=MaschinenStatus.VERFUEGBAR,
    )
    db.add(maschine)
    db.commit()
    db.refresh(maschine)
    db.add(Ausleihe(
        maschine_id=maschine.id,
        benutzer_id=ziel.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
    ))
    db.commit()

    r = client.delete(f"/api/admin/benutzer/{ziel.id}", headers=auth_header(admin))

    assert r.status_code == 409
    assert db.query(Benutzer).filter(Benutzer.id == ziel.id).first() is not None


def test_nicht_vorhandener_benutzer(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN)

    r = client.delete("/api/admin/benutzer/9999", headers=auth_header(admin))

    assert r.status_code == 404


def test_nicht_admin_verboten(client, db):
    mitarbeiter = make_user(db, "max")
    ziel = make_user(db, "anna")

    r = client.delete(f"/api/admin/benutzer/{ziel.id}", headers=auth_header(mitarbeiter))

    assert r.status_code == 403
    assert db.query(Benutzer).filter(Benutzer.id == ziel.id).first() is not None
