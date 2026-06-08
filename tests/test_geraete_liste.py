"""Tests für die Geräte-Übersicht (GET /api/maschinen) für eingeloggte Nutzer."""

from backend.models import Maschine, MaschinenStatus
from .conftest import auth_header, make_user


def _maschine(db, code, name, status=MaschinenStatus.VERFUEGBAR):
    m = Maschine(maschinen_code=code, name=name, status=status)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_mitarbeiter_sieht_alle_maschinen(db, client):
    user = make_user(db, "max")
    _maschine(db, "M-0001", "Bohrmaschine", MaschinenStatus.VERFUEGBAR)
    _maschine(db, "M-0002", "Kreissäge", MaschinenStatus.DEFEKT)

    r = client.get("/api/maschinen", headers=auth_header(user))

    assert r.status_code == 200
    codes = [m["maschinen_code"] for m in r.json()]
    assert codes == ["M-0001", "M-0002"]  # sortiert nach Code, inkl. defekt


def test_geraete_liste_ohne_login_401(db, client):
    r = client.get("/api/maschinen")
    assert r.status_code == 401
