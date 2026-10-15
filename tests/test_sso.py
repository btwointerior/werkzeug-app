"""Portal-SSO: GET /sso/token tauscht signierte X-B2-Header gegen ein Werkzeug-Token."""
import time

from backend import sso
from backend.models import Rolle
from tests.conftest import make_user

SEC = "test-sso-secret-test-sso-secret-1"


def _hdr(kuerzel="fb", rolle="admin", sec=SEC, ts=None, name="Fredy%20B%C3%BChler"):
    return {"X-B2-User": kuerzel, "X-B2-Role": rolle, "X-B2-Email": "", "X-B2-Name": name, "X-B2-Auth": sso.signatur(sec, kuerzel, rolle, "", ts)}


def test_sso_token_fuer_bekanntes_kuerzel(client, db, monkeypatch):
    monkeypatch.setenv("B2_SSO_SECRET", SEC)
    make_user(db, "FB", rolle=Rolle.ADMIN)
    r = client.get("/sso/token", headers=_hdr("fb"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["benutzer"]["benutzername"] == "FB" and d["benutzer"]["rolle"] == "admin"
    assert client.get("/api/me", headers={"Authorization": f"Bearer {d['access_token']}"}).status_code == 200


def test_sso_token_unbekannt_gesperrt_oder_falsch(client, db, monkeypatch):
    monkeypatch.setenv("B2_SSO_SECRET", SEC)
    make_user(db, "sh", aktiv=False)
    assert client.get("/sso/token", headers=_hdr("sh")).status_code == 401  # gesperrt
    assert client.get("/sso/token", headers=_hdr("fb", sec="anderes-secret-anderes-secret-1")).status_code == 401
    assert client.get("/sso/token", headers=_hdr("fb", ts=int(time.time()) - 1000)).status_code == 401
    assert client.get("/sso/token").status_code == 401


def test_sso_ohne_secret_aus(client, db, monkeypatch):
    monkeypatch.delenv("B2_SSO_SECRET", raising=False)
    make_user(db, "fb")
    assert client.get("/sso/token", headers=_hdr("fb")).status_code == 401


def test_sso_legt_benutzer_an_und_gleicht_rolle_ab(client, db, monkeypatch):
    from backend.models import Benutzer, Rolle
    monkeypatch.setenv("B2_SSO_SECRET", SEC)
    r = client.get("/sso/token", headers=_hdr("neu42", rolle="mitarbeiter", name="Max%20M%C3%BCller"))
    assert r.status_code == 200, r.text
    b = db.query(Benutzer).filter(Benutzer.benutzername == "neu42").first()
    assert b and b.vorname == "Max" and b.nachname == "Müller" and b.rolle == Rolle.MITARBEITER and b.passwort_klartext is None
    # Rolle folgt dem Portal
    assert client.get("/sso/token", headers=_hdr("neu42", rolle="admin")).json()["benutzer"]["rolle"] == "admin"
    db.refresh(b); assert b.rolle == Rolle.ADMIN
    assert client.get("/sso/token", headers=_hdr("neu42", rolle="mitarbeiter")).json()["benutzer"]["rolle"] == "mitarbeiter"
