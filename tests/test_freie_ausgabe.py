"""Tests für die Freie Ausgabe (Geräte ohne eigenen Code, Pflicht-Foto)."""

import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

from backend.config import settings
from backend.models import ExternesTeam, FreieAusgabe, Rolle
from tests.conftest import auth_header, make_user


def _jpeg(farbe=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), farbe).save(buf, "JPEG")
    return buf.getvalue()


def _dateien(*inhalte):
    return [("dateien", (f"f{i}.jpg", b, "image/jpeg")) for i, b in enumerate(inhalte)]


def _aufraeumen(daten):
    for f in daten.get("fotos", []):
        (settings.UPLOAD_DIR / f"ausgabe_{daten['id']}_foto_{f['id']}.jpg").unlink(missing_ok=True)


@pytest.fixture()
def admin(db):
    return make_user(db, "admin", rolle=Rolle.ADMIN)


@pytest.fixture()
def max_(db):
    return make_user(db, "max")


@pytest.fixture()
def anna(db):
    return make_user(db, "anna")


def _anlegen(client, user, beschreibung="2 Schraubzwingen 300 mm", team=None, fotos=1):
    data = {"beschreibung": beschreibung}
    if team is not None:
        data["externes_team"] = team
    return client.post(
        "/api/freie-ausgaben",
        data=data,
        files=_dateien(*[_jpeg() for _ in range(fotos)]),
        headers=auth_header(user),
    )


# ---------------- Anlegen ----------------

def test_anlegen_mit_foto(client, max_):
    r = _anlegen(client, max_)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["beschreibung"] == "2 Schraubzwingen 300 mm"
    assert d["benutzer"]["benutzername"] == "max"
    assert d["externes_team_name"] is None
    assert d["ist_offen"] is True
    assert d["rueckgabe_zeitpunkt"] is None
    assert len(d["fotos"]) == 1
    assert d["fotos"][0]["url"].startswith("/uploads/ausgabe_")
    assert "?t=" in d["fotos"][0]["url"]
    pfad = settings.UPLOAD_DIR / f"ausgabe_{d['id']}_foto_{d['fotos'][0]['id']}.jpg"
    assert pfad.is_file()
    _aufraeumen(d)


def test_anlegen_ohne_foto_ist_400(client, max_):
    r = client.post(
        "/api/freie-ausgaben",
        data={"beschreibung": "1 Spritze"},
        headers=auth_header(max_),
    )
    assert r.status_code in (400, 422)
    if r.status_code == 400:
        assert "Foto" in r.json()["detail"]


def test_anlegen_leere_beschreibung_ist_400(client, max_):
    r = _anlegen(client, max_, beschreibung="   ")
    assert r.status_code == 400
    assert "Beschreibung" in r.json()["detail"]


def test_anlegen_mehr_als_drei_fotos_ist_400(client, max_):
    r = _anlegen(client, max_, fotos=4)
    assert r.status_code == 400


def test_anlegen_kein_bild_ist_400(client, max_):
    r = client.post(
        "/api/freie-ausgaben",
        data={"beschreibung": "x"},
        files=[("dateien", ("f.jpg", b"kein bild", "image/jpeg"))],
        headers=auth_header(max_),
    )
    assert r.status_code == 400


def test_anlegen_fuer_externes_team_find_or_create(client, db, max_):
    r = _anlegen(client, max_, team="Team Müller")
    assert r.status_code == 201
    assert r.json()["externes_team_name"] == "Team Müller"
    _aufraeumen(r.json())
    r2 = _anlegen(client, max_, team="Team Müller")
    _aufraeumen(r2.json())
    assert db.query(ExternesTeam).filter_by(name="Team Müller").count() == 1


def test_anlegen_ohne_login_ist_401(client):
    r = client.post("/api/freie-ausgaben", data={"beschreibung": "x"},
                    files=_dateien(_jpeg()))
    assert r.status_code == 401


# ---------------- Meine ----------------

def test_meine_zeigt_nur_eigene_offene(client, max_, anna):
    a = _anlegen(client, max_).json()
    b = _anlegen(client, anna, beschreibung="Annas Zwinge").json()
    r = client.get("/api/freie-ausgaben/meine", headers=auth_header(max_))
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert ids == [a["id"]]
    _aufraeumen(a)
    _aufraeumen(b)


# ---------------- Zurückgeben ----------------

def test_zurueckgeben_durch_eigentuemer(client, max_):
    a = _anlegen(client, max_).json()
    r = client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben",
                    json={"kommentar": "eine verbogen"}, headers=auth_header(max_))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ist_offen"] is False
    assert d["rueckgabe_zeitpunkt"] is not None
    assert d["rueckgabe_kommentar"] == "eine verbogen"
    # verschwindet aus "meine"
    assert client.get("/api/freie-ausgaben/meine", headers=auth_header(max_)).json() == []
    _aufraeumen(a)


def test_zurueckgeben_durch_fremden_ist_403(client, max_, anna):
    a = _anlegen(client, max_).json()
    r = client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben",
                    json={}, headers=auth_header(anna))
    assert r.status_code == 403
    _aufraeumen(a)


def test_zurueckgeben_durch_admin_erlaubt(client, max_, admin):
    a = _anlegen(client, max_).json()
    r = client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben",
                    json={}, headers=auth_header(admin))
    assert r.status_code == 200
    _aufraeumen(a)


def test_zurueckgeben_doppelt_ist_400(client, max_):
    a = _anlegen(client, max_).json()
    client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben", json={}, headers=auth_header(max_))
    r = client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben", json={}, headers=auth_header(max_))
    assert r.status_code == 400
    _aufraeumen(a)


def test_zurueckgeben_unbekannt_ist_404(client, max_):
    r = client.post("/api/freie-ausgaben/9999/zurueckgeben", json={}, headers=auth_header(max_))
    assert r.status_code == 404


# ---------------- Admin-Historie ----------------

def test_admin_liste_filter_und_suche(client, max_, admin):
    a = _anlegen(client, max_, beschreibung="2 Schraubzwingen").json()
    b = _anlegen(client, max_, beschreibung="1 Kartuschenspritze").json()
    client.post(f"/api/freie-ausgaben/{b['id']}/zurueckgeben", json={}, headers=auth_header(max_))

    alle = client.get("/api/admin/freie-ausgaben", headers=auth_header(admin)).json()
    assert [e["id"] for e in alle] == [b["id"], a["id"]]  # neueste zuerst

    offen = client.get("/api/admin/freie-ausgaben?offen=true", headers=auth_header(admin)).json()
    assert [e["id"] for e in offen] == [a["id"]]

    zu = client.get("/api/admin/freie-ausgaben?offen=false", headers=auth_header(admin)).json()
    assert [e["id"] for e in zu] == [b["id"]]

    suche = client.get("/api/admin/freie-ausgaben?suche=spritze", headers=auth_header(admin)).json()
    assert [e["id"] for e in suche] == [b["id"]]

    # Nicht-Admin bekommt 403
    assert client.get("/api/admin/freie-ausgaben", headers=auth_header(max_)).status_code == 403
    _aufraeumen(a)
    _aufraeumen(b)


# ---------------- Statistiken ----------------

def test_statistiken_zaehlen_freie_ausgaben(client, db, max_, admin):
    a = _anlegen(client, max_).json()
    alt = _anlegen(client, max_, beschreibung="alte Zwinge").json()
    zeile = db.query(FreieAusgabe).get(alt["id"])
    zeile.ausgabe_zeitpunkt = datetime.utcnow() - timedelta(days=9)
    db.commit()

    s = client.get("/api/admin/statistiken", headers=auth_header(admin)).json()
    assert s["offene_freie_anzahl"] == 2
    assert [e["id"] for e in s["ueberfaellige_freie"]] == [alt["id"]]
    assert s["ueberfaellige_freie"][0]["beschreibung"] == "alte Zwinge"
    assert s["ueberfaellige_freie"][0]["dauer_tage"] >= 9
    _aufraeumen(a)
    _aufraeumen(alt)


# ---------------- Benutzer löschen ----------------

def test_benutzer_mit_offener_freier_ausgabe_nicht_loeschbar(client, max_, admin):
    a = _anlegen(client, max_).json()
    r = client.delete(f"/api/admin/benutzer/{max_.id}", headers=auth_header(admin))
    assert r.status_code == 409
    client.post(f"/api/freie-ausgaben/{a['id']}/zurueckgeben", json={}, headers=auth_header(max_))
    r = client.delete(f"/api/admin/benutzer/{max_.id}", headers=auth_header(admin))
    assert r.status_code == 204
    _aufraeumen(a)
