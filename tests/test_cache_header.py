"""Oberfläche wird nicht vom Browser zwischengespeichert (sonst fehlen nach einem Deploy neue Funktionen)."""

from backend.models import Rolle
from tests.conftest import auth_header, make_user


def test_statische_dateien_und_startseite_mit_no_cache(client):
    for pfad in ("/static/js/app.js", "/static/js/views/admin_dashboard.js", "/", "/irgendwas"):
        r = client.get(pfad)
        assert r.status_code == 200, pfad
        assert r.headers["cache-control"] == "no-cache", pfad
    # ETag bleibt, damit die Nachfrage mit 304 beantwortet werden kann
    r = client.get("/static/js/app.js")
    assert client.get("/static/js/app.js", headers={"If-None-Match": r.headers["etag"]}).status_code == 304


def test_api_bekommt_keine_cache_vorgabe(client, db):
    admin = make_user(db, "admin", rolle=Rolle.ADMIN)
    r = client.get("/api/me", headers=auth_header(admin))
    assert r.status_code == 200
    assert "cache-control" not in r.headers
