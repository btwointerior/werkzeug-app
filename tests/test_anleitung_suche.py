"""Tests für die automatische Anleitungs-Suche (Websuche gemockt)."""

import urllib.parse

import pytest

from backend import anleitung_suche
from backend.config import settings
from backend.models import Maschine, Rolle
from tests.conftest import auth_header, make_user

MINI_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture()
def admin(db):
    return make_user(db, "admin", rolle=Rolle.ADMIN)


@pytest.fixture()
def maschine(db):
    m = Maschine(maschinen_code="M-200", name="TOP 21", hersteller="Lamello")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_endpunkt_erfolg(client, admin, maschine, monkeypatch):
    monkeypatch.setattr(anleitung_suche, "suche_anleitung",
                        lambda h, n: (MINI_PDF, "https://lamello.com/top21.pdf"))
    r = client.post(f"/api/admin/maschinen/{maschine.id}/anleitung-suche",
                    headers=auth_header(admin))
    assert r.status_code == 200
    d = r.json()
    assert d["anleitung_pfad"] == f"maschine_{maschine.id}_anleitung.pdf"
    assert d["anleitung_url"].startswith("/uploads/")
    pfad = settings.UPLOAD_DIR / d["anleitung_pfad"]
    assert pfad.read_bytes() == MINI_PDF
    pfad.unlink()


def test_endpunkt_nichts_gefunden(client, admin, maschine, monkeypatch):
    def nix(h, n):
        raise anleitung_suche.AnleitungNichtGefunden("Keine passende PDF-Anleitung gefunden.")
    monkeypatch.setattr(anleitung_suche, "suche_anleitung", nix)
    r = client.post(f"/api/admin/maschinen/{maschine.id}/anleitung-suche",
                    headers=auth_header(admin))
    assert r.status_code == 404
    assert "gefunden" in r.json()["detail"]


def test_endpunkt_ohne_hersteller(client, admin, db):
    m = Maschine(maschinen_code="M-201", name="Ohne Hersteller")
    db.add(m)
    db.commit()
    r = client.post(f"/api/admin/maschinen/{m.id}/anleitung-suche",
                    headers=auth_header(admin))
    assert r.status_code == 400
    assert "Hersteller" in r.json()["detail"]


def test_endpunkt_nur_admin(client, db, maschine):
    user = make_user(db, "normalo", rolle=Rolle.MITARBEITER)
    r = client.post(f"/api/admin/maschinen/{maschine.id}/anleitung-suche",
                    headers=auth_header(user))
    assert r.status_code == 403


# ---- Such-/Lade-Logik (urllib gemockt) ----

def _ddg_html(*urls):
    links = "".join(
        f'<a class="result__a" href="/l/?uddg={urllib.parse.quote(u, safe="")}">x</a>'
        for u in urls
    )
    return f"<html><body>{links}</body></html>".encode()


def test_suche_bevorzugt_hersteller_domain(monkeypatch):
    antworten = {
        "html.duckduckgo.com": _ddg_html(
            "https://fremdhost.com/irgendwas.pdf",
            "https://www.lamello.com/anleitung-top21.pdf",
        ),
        "www.lamello.com": MINI_PDF,
        "fremdhost.com": MINI_PDF,
    }

    def fake_hole(url, max_bytes):
        host = urllib.parse.urlparse(url).netloc
        return antworten[host]
    monkeypatch.setattr(anleitung_suche, "_hole", fake_hole)

    daten, quelle = anleitung_suche.suche_anleitung("Lamello", "TOP 21")
    assert daten == MINI_PDF
    assert "lamello.com" in quelle  # Hersteller-Domain gewinnt trotz Platz 2


def test_suche_ueberspringt_nicht_pdf(monkeypatch):
    def fake_hole(url, max_bytes):
        host = urllib.parse.urlparse(url).netloc
        if host == "html.duckduckgo.com":
            return _ddg_html("https://a.com/fake.pdf", "https://b.com/echt.pdf")
        if host == "a.com":
            return b"<html>404-Seite</html>"  # kein PDF
        return MINI_PDF
    monkeypatch.setattr(anleitung_suche, "_hole", fake_hole)

    daten, quelle = anleitung_suche.suche_anleitung("Bosch", "GBH 18V")
    assert daten == MINI_PDF and "b.com" in quelle


def test_suche_keine_treffer(monkeypatch):
    monkeypatch.setattr(anleitung_suche, "_hole", lambda u, m: b"<html>nix</html>")
    with pytest.raises(anleitung_suche.AnleitungNichtGefunden):
        anleitung_suche.suche_anleitung("Nix", "Da")


def test_suche_zu_gross_ohne_gs(monkeypatch):
    gross = b"%PDF-1.4" + b"x" * (anleitung_suche.MAX_PDF_BYTES + 100)

    def fake_hole(url, max_bytes):
        if "duckduckgo" in url:
            return _ddg_html("https://a.com/gross.pdf")
        return gross
    monkeypatch.setattr(anleitung_suche, "_hole", fake_hole)
    monkeypatch.setattr(anleitung_suche.shutil, "which", lambda n: None)  # kein gs
    with pytest.raises(anleitung_suche.AnleitungNichtGefunden):
        anleitung_suche.suche_anleitung("A", "B")
