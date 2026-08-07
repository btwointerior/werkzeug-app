"""Tests für die Foto-Galerie (mehrere Fotos je Maschine, Startbild-Logik)."""

import io

import pytest
from PIL import Image

from backend.config import settings
from backend.models import Maschine, Rolle
from tests.conftest import auth_header, make_user


def _jpeg(farbe=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), farbe).save(buf, "JPEG")
    return buf.getvalue()


def _dateien(*inhalte):
    return [("dateien", (f"f{i}.jpg", b, "image/jpeg")) for i, b in enumerate(inhalte)]


@pytest.fixture()
def admin(db):
    return make_user(db, "admin", rolle=Rolle.ADMIN)


@pytest.fixture()
def maschine(db):
    m = Maschine(maschinen_code="M-100", name="Testmaschine")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _aufraeumen(daten):
    for f in daten.get("fotos", []):
        pfad = settings.UPLOAD_DIR / f"maschine_{daten['id']}_foto_{f['id']}.jpg"
        pfad.unlink(missing_ok=True)


def test_mehrere_fotos_hochladen_erstes_wird_start(client, admin, maschine):
    r = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg(), _jpeg((0, 0, 200)), _jpeg((0, 200, 0))),
                    headers=auth_header(admin))
    assert r.status_code == 200
    d = r.json()
    assert len(d["fotos"]) == 3
    assert [f["ist_start"] for f in d["fotos"]] == [True, False, False]
    assert d["foto_pfad"] == f"maschine_{maschine.id}_foto_{d['fotos'][0]['id']}.jpg"
    assert all(f["url"].startswith("/uploads/") for f in d["fotos"])
    _aufraeumen(d)


def test_start_index_beim_upload(client, admin, maschine):
    r = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg(), _jpeg((0, 0, 200))),
                    data={"start_index": "1"},
                    headers=auth_header(admin))
    d = r.json()
    assert [f["ist_start"] for f in d["fotos"]] == [False, True]
    assert d["foto_pfad"].endswith(f"_{d['fotos'][1]['id']}.jpg")
    _aufraeumen(d)


def test_startbild_wechseln(client, admin, maschine):
    d = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg(), _jpeg((0, 0, 200))),
                    headers=auth_header(admin)).json()
    zweites = d["fotos"][1]["id"]
    r = client.put(f"/api/admin/maschinen/{maschine.id}/fotos/{zweites}/start",
                   headers=auth_header(admin))
    assert r.status_code == 200
    d2 = r.json()
    assert [f["ist_start"] for f in d2["fotos"]] == [False, True]
    assert d2["foto_pfad"].endswith(f"_{zweites}.jpg")
    _aufraeumen(d2)


def test_startbild_loeschen_naechstes_rueckt_nach(client, admin, maschine):
    d = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg(), _jpeg((0, 0, 200))),
                    headers=auth_header(admin)).json()
    erstes = d["fotos"][0]["id"]
    r = client.delete(f"/api/admin/maschinen/{maschine.id}/fotos/{erstes}",
                      headers=auth_header(admin))
    assert r.status_code == 200
    d2 = r.json()
    assert len(d2["fotos"]) == 1
    assert d2["fotos"][0]["ist_start"] is True
    assert d2["foto_pfad"].endswith(f"_{d2['fotos'][0]['id']}.jpg")
    # Datei des gelöschten Fotos ist weg
    assert not (settings.UPLOAD_DIR / f"maschine_{maschine.id}_foto_{erstes}.jpg").exists()
    _aufraeumen(d2)


def test_letztes_foto_loeschen_leert_foto_pfad(client, admin, maschine):
    d = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg()), headers=auth_header(admin)).json()
    r = client.delete(f"/api/admin/maschinen/{maschine.id}/fotos/{d['fotos'][0]['id']}",
                      headers=auth_header(admin))
    d2 = r.json()
    assert d2["fotos"] == []
    assert d2["foto_pfad"] is None


def test_alt_endpunkt_foto_wird_galerie_start(client, admin, maschine):
    """POST /foto (Alt-Endpunkt, KI-Flow v1.1.x) legt Galerie-Foto + Startbild an."""
    r = client.post(f"/api/admin/maschinen/{maschine.id}/foto",
                    files={"datei": ("f.jpg", _jpeg(), "image/jpeg")},
                    headers=auth_header(admin))
    assert r.status_code == 200
    d = r.json()
    assert len(d["fotos"]) == 1 and d["fotos"][0]["ist_start"] is True
    assert d["foto_pfad"] == f"maschine_{maschine.id}_foto_{d['fotos'][0]['id']}.jpg"
    # Zweiter Upload ersetzt das Startbild (haengt an + neues Startbild)
    r2 = client.post(f"/api/admin/maschinen/{maschine.id}/foto",
                     files={"datei": ("g.jpg", _jpeg((0, 0, 200)), "image/jpeg")},
                     headers=auth_header(admin))
    d2 = r2.json()
    assert len(d2["fotos"]) == 2
    assert [f["ist_start"] for f in d2["fotos"]] == [False, True]
    _aufraeumen(d2)


def test_fotos_ungueltige_datei(client, admin, maschine):
    r = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(b"kein bild"), headers=auth_header(admin))
    assert r.status_code == 400


def test_fotos_nur_admin(client, db, maschine):
    user = make_user(db, "normalo", rolle=Rolle.MITARBEITER)
    r = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg()), headers=auth_header(user))
    assert r.status_code == 403


def test_start_auf_fremdes_foto_404(client, admin, maschine):
    r = client.put(f"/api/admin/maschinen/{maschine.id}/fotos/9999/start",
                   headers=auth_header(admin))
    assert r.status_code == 404


def test_maschine_loeschen_entfernt_fotodateien(client, admin, maschine, db):
    d = client.post(f"/api/admin/maschinen/{maschine.id}/fotos",
                    files=_dateien(_jpeg(), _jpeg((0, 0, 200))),
                    headers=auth_header(admin)).json()
    pfade = [settings.UPLOAD_DIR / f"maschine_{maschine.id}_foto_{f['id']}.jpg"
             for f in d["fotos"]]
    assert all(p.exists() for p in pfade)
    r = client.delete(f"/api/admin/maschinen/{maschine.id}", headers=auth_header(admin))
    assert r.status_code == 204
    assert not any(p.exists() for p in pfade)
