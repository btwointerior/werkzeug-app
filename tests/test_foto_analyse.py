"""Tests für POST /api/admin/maschinen/foto-analyse + backend/ki_analyse.py."""

import io

import pytest
from PIL import Image

from backend import ki_analyse
from tests.conftest import auth_header, make_user
from backend.models import Rolle

URL = "/api/admin/maschinen/foto-analyse"


def _jpeg_bytes(farbe=(200, 30, 30), groesse=(80, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, "JPEG")
    return buf.getvalue()


def _dateien(*inhalte, content_type="image/jpeg"):
    return [("dateien", (f"foto{i}.jpg", inhalt, content_type))
            for i, inhalt in enumerate(inhalte)]


@pytest.fixture()
def admin(db):
    return make_user(db, "admin", rolle=Rolle.ADMIN)


@pytest.fixture()
def _ki_ok(monkeypatch):
    """KI 'konfiguriert' + Bedrock-Aufruf gemockt."""
    monkeypatch.setattr(ki_analyse, "ist_konfiguriert", lambda: True)
    monkeypatch.setattr(
        ki_analyse,
        "_rufe_bedrock",
        lambda bilder: '{"name": "Lamello TOP 21", "hersteller": "Lamello",'
                       ' "seriennummer": "L44E-1617318", "beschreibung": "Flachdübelfräse",'
                       ' "hinweis": null}',
    )


# ---- Endpunkt ----

def test_analyse_erfolg(client, admin, _ki_ok):
    r = client.post(URL, files=_dateien(_jpeg_bytes(), _jpeg_bytes((10, 10, 200))),
                    headers=auth_header(admin))
    assert r.status_code == 200
    daten = r.json()
    assert daten["name"] == "Lamello TOP 21"
    assert daten["hersteller"] == "Lamello"
    assert daten["seriennummer"] == "L44E-1617318"
    assert daten["hinweis"] is None


def test_analyse_nichts_erkannt(client, admin, monkeypatch):
    monkeypatch.setattr(ki_analyse, "ist_konfiguriert", lambda: True)
    monkeypatch.setattr(
        ki_analyse, "_rufe_bedrock",
        lambda bilder: '{"name": null, "hersteller": null, "seriennummer": null,'
                       ' "beschreibung": null, "hinweis": "Kein Typenschild erkennbar."}',
    )
    r = client.post(URL, files=_dateien(_jpeg_bytes()), headers=auth_header(admin))
    assert r.status_code == 200
    assert r.json()["name"] is None
    assert "Typenschild" in r.json()["hinweis"]


def test_analyse_nicht_konfiguriert(client, admin, monkeypatch):
    for var in ("WERKZEUG_KI_MOCK", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(var, raising=False)
    r = client.post(URL, files=_dateien(_jpeg_bytes()), headers=auth_header(admin))
    assert r.status_code == 503
    assert "nicht konfiguriert" in r.json()["detail"]


def test_analyse_bedrock_fehler(client, admin, monkeypatch):
    monkeypatch.setattr(ki_analyse, "ist_konfiguriert", lambda: True)

    def kaputt(bilder):
        raise ki_analyse.KIAnalyseFehler("KI-Dienst ist gerade nicht erreichbar.")
    monkeypatch.setattr(ki_analyse, "_rufe_bedrock", kaputt)
    r = client.post(URL, files=_dateien(_jpeg_bytes()), headers=auth_header(admin))
    assert r.status_code == 503
    assert "nicht erreichbar" in r.json()["detail"]


def test_analyse_ungueltiges_bild(client, admin, _ki_ok):
    r = client.post(URL, files=_dateien(b"kein bild"), headers=auth_header(admin))
    assert r.status_code == 400
    assert "kein gültiges Bild" in r.json()["detail"]


def test_analyse_falscher_typ(client, admin, _ki_ok):
    r = client.post(URL, files=_dateien(_jpeg_bytes(), content_type="application/pdf"),
                    headers=auth_header(admin))
    assert r.status_code == 400


def test_analyse_zu_viele_fotos(client, admin, _ki_ok):
    r = client.post(URL, files=_dateien(*[_jpeg_bytes()] * 6), headers=auth_header(admin))
    assert r.status_code == 400
    assert "1 bis 5" in r.json()["detail"]


def test_analyse_nur_admin(client, db, _ki_ok):
    user = make_user(db, "normalo", rolle=Rolle.MITARBEITER)
    r = client.post(URL, files=_dateien(_jpeg_bytes()), headers=auth_header(user))
    assert r.status_code == 403


def test_analyse_mock_modus(client, admin, monkeypatch):
    monkeypatch.setenv("WERKZEUG_KI_MOCK", "1")
    r = client.post(URL, files=_dateien(_jpeg_bytes()), headers=auth_header(admin))
    assert r.status_code == 200
    assert r.json()["seriennummer"] == "L44E-1617318"
    assert "Mock" in r.json()["hinweis"]


# ---- _parse_antwort ----

def test_parse_mit_codefence():
    text = '```json\n{"name": "Festool EHL 65 EQ-Plus", "hersteller": "Festool",' \
           ' "seriennummer": "576601", "beschreibung": null, "hinweis": null}\n```'
    d = ki_analyse._parse_antwort(text)
    assert d["name"] == "Festool EHL 65 EQ-Plus"
    assert d["seriennummer"] == "576601"


def test_parse_mit_drumherum_text():
    d = ki_analyse._parse_antwort('Hier das Ergebnis: {"name": "X", "hersteller": "Y"}')
    assert d["name"] == "X"
    assert d["seriennummer"] is None


def test_parse_leere_strings_werden_null():
    d = ki_analyse._parse_antwort('{"name": "  ", "hersteller": ""}')
    assert d["name"] is None
    assert d["hersteller"] is None


def test_parse_laengen_begrenzt():
    d = ki_analyse._parse_antwort('{"seriennummer": "' + "9" * 200 + '"}')
    assert len(d["seriennummer"]) == 80


def test_parse_kein_json():
    with pytest.raises(ki_analyse.KIAnalyseFehler):
        ki_analyse._parse_antwort("Ich konnte nichts erkennen, sorry.")


def test_parse_kaputtes_json():
    with pytest.raises(ki_analyse.KIAnalyseFehler):
        ki_analyse._parse_antwort('{"name": "abbruch...')
