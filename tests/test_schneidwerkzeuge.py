"""Tests für die Schneidwerkzeuge (Sägeblätter, Fräser …): Bestand, Status, Schärfkreislauf."""

import pytest

from backend.models import Rolle
from backend.schneidwerkzeug_models import SchaerfAuftrag, Schneidwerkzeug, SchneidwerkzeugEreignis
from tests.conftest import auth_header, make_user

API = "/api/schneidwerkzeuge"
SCHAERF = "/api/schaerfauftraege"


@pytest.fixture()
def admin(db):
    return make_user(db, "admin", rolle=Rolle.ADMIN)


@pytest.fixture()
def max_(db):
    return make_user(db, "max")


def _neu(client, admin, **felder):
    daten = {"art": "saegeblatt", "bezeichnung": "Plattenaufteilblatt 300 Z72", **felder}
    r = client.post(API, json=daten, headers=auth_header(admin))
    assert r.status_code == 201, r.text
    return r.json()


def _status(client, user, wid, **felder):
    return client.post(f"{API}/{wid}/status", json=felder, headers=auth_header(user))


# ---- Anlegen, Codes, Rechte ----

def test_anlegen_vergibt_code_je_art_und_schreibt_ereignis(client, db, admin):
    a = _neu(client, admin, hersteller="Leitz", durchmesser_mm=300, zaehnezahl=72, schneidstoff="HW",
             max_schaerfungen=15, kaufpreis_cent=18900, kaufdatum="2026-03-01", lagerort="Schrank 1 / Fach 3")
    assert a["code"] == "SB-001"
    assert a["status"] == "lager" and a["status_text"] == "Im Lager (scharf)"
    assert a["art_text"] == "Sägeblatt"
    assert a["anzahl_schaerfungen"] == 0 and a["rest_schaerfungen"] == 15 and a["schaerfkosten_cent"] == 0
    assert a["ereignisse"][0]["art"] == "angelegt"
    assert _neu(client, admin)["code"] == "SB-002"
    assert _neu(client, admin, art="fraeser", bezeichnung="Schaftfräser 12 mm DP")["code"] == "FR-001"
    assert _neu(client, admin, code="sb-040")["code"] == "SB-040"
    assert _neu(client, admin)["code"] == "SB-041"


def test_anlegen_validierung_und_rechte(client, admin, max_):
    h = auth_header(admin)
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": "x"}, headers=auth_header(max_)).status_code == 403
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": "x"}).status_code == 401
    assert client.post(API, json={"art": "quatsch", "bezeichnung": "x"}, headers=h).status_code == 400
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": ""}, headers=h).status_code == 422
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": "x", "code": "M-001"}, headers=h).status_code == 400
    _neu(client, admin, code="SB-007")
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": "x", "code": "SB-007"}, headers=h).status_code == 409
    assert client.post(API, json={"art": "saegeblatt", "bezeichnung": "x", "partner_code": "VR-999"}, headers=h).status_code == 400


def test_satz_aus_saegeblatt_und_vorritzer(client, admin):
    blatt = _neu(client, admin)
    ritzer = _neu(client, admin, art="vorritzer", bezeichnung="Vorritzer 180", partner_code=blatt["code"])
    assert ritzer["partner_code"] == "SB-001"
    # Die Verknüpfung gilt in beide Richtungen, auch wenn sie nur beim Vorritzer eingetragen ist.
    assert client.get(f"{API}/{blatt['id']}", headers=auth_header(admin)).json()["partner_code"] == "VR-001"
    r = client.put(f"{API}/{blatt['id']}", json={"art": "saegeblatt", "bezeichnung": "Plattenaufteilblatt 300 Z72", "partner_code": "SB-001"},
                   headers=auth_header(admin))
    assert r.status_code == 400  # nicht sein eigener Partner


def test_liste_suche_filter_und_code_abruf(client, admin, max_):
    a = _neu(client, admin, hersteller="Leitz", artikelnummer="LZ-300-72")
    b = _neu(client, admin, art="fraeser", bezeichnung="Schaftfräser 12 mm")
    _status(client, admin, b["id"], status="verschrottet")
    h = auth_header(max_)
    assert [w["code"] for w in client.get(API, headers=h).json()] == ["SB-001"]          # ohne Verschrottete
    assert len(client.get(f"{API}?status=alle", headers=h).json()) == 2
    assert [w["code"] for w in client.get(f"{API}?status=verschrottet", headers=h).json()] == ["FR-001"]
    assert [w["code"] for w in client.get(f"{API}?suche=lz-300", headers=h).json()] == ["SB-001"]
    assert client.get(f"{API}?art=fraeser", headers=h).json() == []
    assert client.get(f"{API}/code/sb-001", headers=h).json()["id"] == a["id"]
    assert client.get(f"{API}/code/SB-999", headers=h).status_code == 404
    assert client.get(API).status_code == 401


def test_stammwerte_liefern_arten_naechste_codes_und_vorschlaege(client, admin, max_):
    w = _neu(client, admin, lagerort="Schrank 1")
    _status(client, max_, w["id"], status="maschine", maschine="Plattensäge", platz="Hauptsäge")
    s = client.get(f"{API}/stammwerte", headers=auth_header(max_)).json()
    assert s["naechste_codes"]["saegeblatt"] == "SB-002" and s["naechste_codes"]["fraeser"] == "FR-001"
    assert s["maschinen"] == ["CNC liegend", "CNC stehend", "Plattensäge", "Kreissäge", "Tischkreissäge", "Kappsäge", "Kantenanleimmaschine"]
    assert s["lagerorte"] == ["Schrank 1"]
    assert s["dienste"] == ["Bukara", "Leuco"] and "MDF" in s["materialien"]
    assert [e["key"] for e in s["ergebnisse"]] == ["geschaerft", "neu_bestueckt", "ausgemustert"]
    assert {a["key"] for a in s["arten"]} == {"saegeblatt", "vorritzer", "fraeser", "bohrer", "messer", "sonstiges"}


# ---- Status ----

def test_statuswechsel_einbauen_stumpf_lager(client, db, admin, max_):
    w = _neu(client, admin, lagerort="Schrank 1")
    r = _status(client, max_, w["id"], status="maschine")
    assert r.status_code == 400 and "Maschine" in r.json()["detail"]
    d = _status(client, max_, w["id"], status="maschine", maschine="Plattensäge", platz="Hauptsäge").json()
    assert (d["status"], d["maschine"], d["platz"], d["lagerort"]) == ("maschine", "Plattensäge", "Hauptsäge", "Schrank 1")
    assert d["ereignisse"][0]["text"] == "Eingebaut in Plattensäge, Platz Hauptsäge."
    assert d["ereignisse"][0]["benutzer_name"] == "Vor Nach"
    d = _status(client, max_, w["id"], status="stumpf", notiz="Ausrisse an HPL").json()
    assert (d["status"], d["maschine"], d["platz"]) == ("stumpf", None, None)
    assert d["ereignisse"][0]["text"] == "Als stumpf gemeldet. Ausrisse an HPL"
    d = _status(client, max_, w["id"], status="lager", lagerort="Schrank 2").json()
    assert d["lagerort"] == "Schrank 2"
    assert _status(client, max_, w["id"], status="quatsch").status_code == 400
    assert _status(client, max_, w["id"], status="schaerfdienst").status_code == 400
    assert _status(client, max_, 9999, status="lager").status_code == 404


def test_verschrotten_und_reaktivieren_nur_admin(client, admin, max_):
    w = _neu(client, admin)
    assert _status(client, max_, w["id"], status="verschrottet").status_code == 403
    assert _status(client, admin, w["id"], status="verschrottet").json()["status"] == "verschrottet"
    assert _status(client, max_, w["id"], status="lager").status_code == 403
    assert _status(client, admin, w["id"], status="lager").json()["status"] == "lager"


# ---- Schärfkreislauf ----

def test_schaerfauftrag_abgabe_und_rueckkehr(client, db, admin, max_):
    a = _neu(client, admin, max_schaerfungen=2)
    b = _neu(client, admin, art="fraeser", bezeichnung="Fügefräser DP")
    _status(client, max_, a["id"], status="maschine", maschine="Plattensäge")
    h = auth_header(admin)
    r = client.post(SCHAERF, json={"dienst": " Schärfdienst Müller ", "werkzeug_ids": [a["id"], b["id"], a["id"]], "notiz": "Abholung Do"}, headers=h)
    assert r.status_code == 201, r.text
    auftrag = r.json()
    assert auftrag["dienst"] == "Schärfdienst Müller" and auftrag["anzahl"] == 2 and auftrag["ist_offen"] is True
    assert [p["werkzeug_code"] for p in auftrag["positionen"]] == ["FR-001", "SB-001"]
    d = client.get(f"{API}/{a['id']}", headers=h).json()
    assert (d["status"], d["maschine"]) == ("schaerfdienst", None)
    assert d["ereignisse"][0]["text"] == "An Schärfdienst Schärfdienst Müller abgegeben."
    # Solange es weg ist: kein Statuswechsel von Hand, kein zweiter Auftrag
    assert _status(client, max_, a["id"], status="lager").status_code == 409
    assert client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": [a["id"]]}, headers=h).status_code == 409

    # Teilrückgabe: Sägeblatt geschärft
    r = client.post(f"{SCHAERF}/{auftrag['id']}/rueckgabe", headers=h,
                    json={"positionen": [{"werkzeug_id": a["id"], "kosten_cent": 1450, "lagerort": "Schrank 1"}]})
    assert r.status_code == 200, r.text
    assert r.json()["ist_offen"] is True and r.json()["anzahl_zurueck"] == 1 and r.json()["kosten_cent"] == 1450
    d = client.get(f"{API}/{a['id']}", headers=h).json()
    assert (d["status"], d["lagerort"], d["anzahl_schaerfungen"], d["rest_schaerfungen"], d["schaerfkosten_cent"]) == ("lager", "Schrank 1", 1, 1, 1450)
    assert d["ereignisse"][0]["text"] == "Vom Schärfdienst Schärfdienst Müller zurück, geschärft, 14,50 €. Noch 1 Schärfung(en) möglich."
    assert d["schaerfpositionen"][0]["ergebnis"] == "geschaerft"
    # dieselbe Position nicht zweimal
    assert client.post(f"{SCHAERF}/{auftrag['id']}/rueckgabe", headers=h, json={"positionen": [{"werkzeug_id": a["id"]}]}).status_code == 409

    # Fräser kommt ausgemustert zurück → verschrottet, Auftrag abgeschlossen
    r = client.post(f"{SCHAERF}/{auftrag['id']}/rueckgabe", headers=h,
                    json={"positionen": [{"werkzeug_id": b["id"], "ergebnis": "ausgemustert", "notiz": "Schneide ausgebrochen"}]})
    assert r.json()["ist_offen"] is False and r.json()["abgeschlossen_am"]
    assert client.get(f"{API}/{b['id']}", headers=h).json()["status"] == "verschrottet"
    assert [x["id"] for x in client.get(f"{SCHAERF}?offen=true", headers=h).json()] == []
    assert len(client.get(f"{SCHAERF}?offen=false", headers=h).json()) == 1


def test_schaerfauftrag_validierung_und_rechte(client, db, admin, max_):
    a = _neu(client, admin)
    h = auth_header(admin)
    assert client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": [a["id"]]}, headers=auth_header(max_)).status_code == 403
    assert client.get(SCHAERF, headers=auth_header(max_)).status_code == 403
    assert client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": []}, headers=h).status_code == 422
    assert client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": [a["id"], 9999]}, headers=h).status_code == 400
    assert db.query(SchaerfAuftrag).count() == 0                      # alles oder nichts
    assert db.query(Schneidwerkzeug).get(a["id"]).status == "lager"
    auftrag = client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": [a["id"]]}, headers=h).json()
    rueck = f"{SCHAERF}/{auftrag['id']}/rueckgabe"
    assert client.post(rueck, headers=h, json={"positionen": [{"werkzeug_id": a["id"], "ergebnis": "quatsch"}]}).status_code == 400
    assert client.post(rueck, headers=h, json={"positionen": [{"werkzeug_id": a["id"]}, {"werkzeug_id": a["id"]}]}).status_code == 400
    assert client.post(rueck, headers=h, json={"positionen": [{"werkzeug_id": 9999}]}).status_code == 409
    assert client.post(f"{SCHAERF}/9999/rueckgabe", headers=h, json={"positionen": [{"werkzeug_id": a["id"]}]}).status_code == 404
    assert db.query(Schneidwerkzeug).get(a["id"]).status == "schaerfdienst"


def test_loeschen_nur_ohne_schaerfhistorie(client, db, admin, max_):
    a = _neu(client, admin)
    b = _neu(client, admin)
    h = auth_header(admin)
    assert client.delete(f"{API}/{a['id']}", headers=auth_header(max_)).status_code == 403
    assert client.delete(f"{API}/{a['id']}", headers=h).status_code == 204
    assert db.query(SchneidwerkzeugEreignis).filter_by(werkzeug_id=a["id"]).count() == 0
    client.post(SCHAERF, json={"dienst": "X", "werkzeug_ids": [b["id"]]}, headers=h)
    assert client.delete(f"{API}/{b['id']}", headers=h).status_code == 409


# ---- Übersicht, Ändern, QR ----

def test_uebersicht_zaehlt_und_meldet_fehlenden_ersatz(client, admin, max_):
    a = _neu(client, admin, artikelnummer="LZ-300")
    b = _neu(client, admin, artikelnummer="LZ-300")
    c = _neu(client, admin, art="fraeser", bezeichnung="Fügefräser DP")
    _status(client, max_, a["id"], status="maschine", maschine="Plattensäge")
    _status(client, max_, c["id"], status="maschine", maschine="CNC liegend")
    u = client.get(f"{API}/uebersicht", headers=auth_header(max_)).json()
    assert u["gesamt"] == 3 and u["je_status"]["maschine"] == 2 and u["je_status"]["lager"] == 1
    assert [g["bezeichnung"] for g in u["ohne_ersatz"]] == ["Fügefräser DP"]   # LZ-300 hat noch eins im Lager
    _status(client, max_, b["id"], status="stumpf")
    u = client.get(f"{API}/uebersicht", headers=auth_header(max_)).json()
    assert len(u["ohne_ersatz"]) == 2 and u["je_status"]["stumpf"] == 1 and u["offene_schaerfauftraege"] == 0


def test_aendern_und_qr_etikett(client, admin, max_):
    a = _neu(client, admin, durchmesser_mm=300, zaehnezahl=72, schneidstoff="HW", max_drehzahl=6000)
    h = auth_header(admin)
    r = client.put(f"{API}/{a['id']}", headers=h, json={"art": "saegeblatt", "bezeichnung": "Neu benannt", "code": "SB-050", "hersteller": " AKE "})
    assert r.status_code == 200 and (r.json()["code"], r.json()["bezeichnung"], r.json()["hersteller"]) == ("SB-050", "Neu benannt", "AKE")
    assert r.json()["ereignisse"][0]["art"] == "geaendert"
    assert client.put(f"{API}/{a['id']}", headers=auth_header(max_), json={"art": "saegeblatt", "bezeichnung": "x"}).status_code == 403
    pdf = client.get(f"{API}/{a['id']}/qr-code", headers=h)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert client.get(f"{API}/{a['id']}/qr-code", headers=auth_header(max_)).status_code == 403


# ---- Ausbau nach den Antworten von fb (2026-11-11) ----

def test_einsatzgebiet_und_parameter_werden_gespeichert_und_gefunden(client, admin, max_):
    w = _neu(client, admin, art="fraeser", bezeichnung="Schaftfräser D12", einsatzgebiet=" Formatieren und Nuten ",
             materialien="Spanplatte, MDF, Spanplatte, ", drehzahl_empfohlen=18000, vorschub_empfohlen=6.5,
             parameter_notiz="Zustellung max. 12 mm, Gegenlauf")
    assert (w["einsatzgebiet"], w["materialien"], w["drehzahl_empfohlen"], w["vorschub_empfohlen"]) == ("Formatieren und Nuten", "Spanplatte, MDF", 18000, 6.5)
    assert w["parameter_notiz"] == "Zustellung max. 12 mm, Gegenlauf" and w["masse_pruefen"] is False
    h = auth_header(max_)
    assert [x["code"] for x in client.get(f"{API}?suche=nuten", headers=h).json()] == ["FR-001"]
    assert [x["code"] for x in client.get(f"{API}?suche=mdf", headers=h).json()] == ["FR-001"]
    assert client.get(f"{API}?suche=aluminium", headers=h).json() == []


def test_einbauen_nur_in_maschinen_der_liste(client, admin, max_):
    w = _neu(client, admin)
    r = _status(client, max_, w["id"], status="maschine", maschine="Bandsäge")
    assert r.status_code == 400 and "Maschinenliste" in r.json()["detail"]
    assert _status(client, max_, w["id"], status="maschine", maschine="kappsäge").json()["maschine"] == "Kappsäge"


def test_maschinenliste_anlegen_umbenennen_abschalten(client, db, admin, max_):
    h = auth_header(admin)
    liste = client.get(f"{API}/maschinen", headers=auth_header(max_)).json()
    assert len(liste) == 7 and all(m["aktiv"] for m in liste)
    stehend = next(m for m in liste if m["name"] == "CNC stehend")
    assert client.post(f"{API}/maschinen", json={"name": "Bandsäge"}, headers=auth_header(max_)).status_code == 403
    assert client.post(f"{API}/maschinen", json={"name": "Bandsäge"}, headers=h).status_code == 201
    assert client.post(f"{API}/maschinen", json={"name": "bandsäge"}, headers=h).status_code == 409
    w = _neu(client, admin, art="fraeser", bezeichnung="Fräser")
    _status(client, max_, w["id"], status="maschine", maschine="CNC stehend")
    # Abschalten geht nicht, solange etwas eingebaut ist
    assert client.put(f"{API}/maschinen/{stehend['id']}", json={"name": "CNC stehend", "aktiv": False}, headers=h).status_code == 409
    # Umbenennen zieht das eingebaute Werkzeug mit
    r = client.put(f"{API}/maschinen/{stehend['id']}", json={"name": "CNC Homag BHX", "aktiv": True}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "CNC Homag BHX"
    assert client.get(f"{API}/{w['id']}", headers=h).json()["maschine"] == "CNC Homag BHX"
    assert client.put(f"{API}/maschinen/{stehend['id']}", json={"name": "Plattensäge", "aktiv": True}, headers=h).status_code == 409
    assert client.put(f"{API}/maschinen/9999", json={"name": "x", "aktiv": True}, headers=h).status_code == 404
    _status(client, max_, w["id"], status="lager")
    assert client.put(f"{API}/maschinen/{stehend['id']}", json={"name": "CNC Homag BHX", "aktiv": False}, headers=h).json()["aktiv"] is False
    assert "CNC Homag BHX" not in client.get(f"{API}/stammwerte", headers=h).json()["maschinen"]


def test_rueckkehr_neu_bestueckt_setzt_schaerfzaehler_zurueck(client, admin):
    h = auth_header(admin)
    w = _neu(client, admin, max_schaerfungen=3)

    def runde(ergebnis):
        a = client.post(SCHAERF, json={"dienst": "Leuco", "werkzeug_ids": [w["id"]]}, headers=h).json()
        r = client.post(f"{SCHAERF}/{a['id']}/rueckgabe", headers=h, json={"positionen": [{"werkzeug_id": w["id"], "ergebnis": ergebnis}]})
        assert r.status_code == 200, r.text
        return client.get(f"{API}/{w['id']}", headers=h).json()

    assert runde("geschaerft")["anzahl_schaerfungen"] == 1
    d = runde("geschaerft")
    assert (d["anzahl_schaerfungen"], d["rest_schaerfungen"]) == (2, 1)
    d = runde("neu_bestueckt")
    assert (d["status"], d["anzahl_schaerfungen"], d["rest_schaerfungen"], d["masse_pruefen"]) == ("lager", 0, 3, False)
    assert "neu bestückt" in d["ereignisse"][0]["text"] and "Schärfzähler beginnt neu" in d["ereignisse"][0]["text"]
    assert runde("geschaerft")["anzahl_schaerfungen"] == 1


def test_rueckkehr_fraeser_neue_masse_und_pruefhinweis(client, admin, max_):
    h = auth_header(admin)
    f = _neu(client, admin, art="fraeser", bezeichnung="Schaftfräser D12", durchmesser_mm=12, schneidenlaenge_mm=35)
    blatt = _neu(client, admin)
    a = client.post(SCHAERF, json={"dienst": "Bukara", "werkzeug_ids": [f["id"], blatt["id"]]}, headers=h).json()
    assert a["positionen"][0]["werkzeug_art"] == "fraeser"
    r = client.post(f"{SCHAERF}/{a['id']}/rueckgabe", headers=h, json={"positionen": [
        {"werkzeug_id": f["id"], "neuer_durchmesser_mm": 11.8, "neue_laenge_mm": 34.5},
        {"werkzeug_id": blatt["id"], "neuer_durchmesser_mm": 290}]})
    assert r.status_code == 200, r.text
    d = client.get(f"{API}/{f['id']}", headers=h).json()
    assert (d["durchmesser_mm"], d["schneidenlaenge_mm"], d["masse_pruefen"]) == (11.8, 34.5, True)
    assert "Neuer Durchmesser 11.8 mm. Neue Länge 34.5 mm. Maße an der CNC prüfen." in d["ereignisse"][0]["text"]
    b = client.get(f"{API}/{blatt['id']}", headers=h).json()
    assert (b["durchmesser_mm"], b["masse_pruefen"]) == (None, False)      # Sägeblätter brauchen das nicht
    u = client.get(f"{API}/uebersicht", headers=h).json()
    assert [x["code"] for x in u["masse_pruefen"]] == ["FR-001"]
    # Abhaken darf jeder Angemeldete; zweimal schadet nicht
    d = client.post(f"{API}/{f['id']}/masse-geprueft", headers=auth_header(max_)).json()
    assert d["masse_pruefen"] is False and d["ereignisse"][0]["text"] == "Maße an der CNC geprüft und eingetragen."
    assert len(client.post(f"{API}/{f['id']}/masse-geprueft", headers=auth_header(max_)).json()["ereignisse"]) == len(d["ereignisse"])
    assert client.get(f"{API}/uebersicht", headers=h).json()["masse_pruefen"] == []


def test_uebersicht_nach_ort_und_fast_aufgebraucht(client, admin, max_):
    h = auth_header(admin)
    a = _neu(client, admin, lagerort="Schrank 1", max_schaerfungen=1)
    b = _neu(client, admin, lagerort="Schrank 2")
    c = _neu(client, admin)
    _status(client, max_, b["id"], status="maschine", maschine="Plattensäge", platz="Hauptsäge")
    u = client.get(f"{API}/uebersicht", headers=h).json()
    maschinen = {m["name"]: m["werkzeuge"] for m in u["nach_ort"]["maschinen"]}
    assert list(maschinen)[:3] == ["CNC liegend", "CNC stehend", "Plattensäge"]     # alle Maschinen, auch leere
    assert maschinen["CNC liegend"] == [] and [(w["code"], w["platz"]) for w in maschinen["Plattensäge"]] == [("SB-002", "Hauptsäge")]
    assert [(g["name"], [w["code"] for w in g["werkzeuge"]]) for g in u["nach_ort"]["lager"]] == [("Schrank 1", ["SB-001"]), ("Ohne Fach", ["SB-003"])]
    assert [(x["code"], x["rest"]) for x in u["fast_aufgebraucht"]] == [("SB-001", 1)]


def test_verbrauchsteile_bestand_entnahme_mindestbestand(client, db, admin, max_):
    V = "/api/verbrauchsteile"
    h, hm = auth_header(admin), auth_header(max_)
    assert client.post(V, json={"bezeichnung": "Fügemesser"}, headers=hm).status_code == 403
    t = client.post(V, json={"bezeichnung": " Fügemesser 20 mm ", "maschine": "Kantenanleimmaschine", "bestand": 6, "mindestbestand": 4, "lagerort": "Schublade 2"}, headers=h).json()
    assert (t["bezeichnung"], t["bestand"], t["unter_mindestbestand"]) == ("Fügemesser 20 mm", 6, False)
    assert t["bewegungen"][0]["text"] == "Anfangsbestand"
    # Entnahme durch Mitarbeiter
    r = client.post(f"{V}/{t['id']}/bewegung", json={"menge": -3, "text": "Messer getauscht"}, headers=hm)
    assert r.status_code == 200 and (r.json()["bestand"], r.json()["unter_mindestbestand"]) == (3, True)
    assert (r.json()["bewegungen"][0]["menge"], r.json()["bewegungen"][0]["benutzer_name"]) == (-3, "Vor Nach")
    assert client.post(f"{V}/{t['id']}/bewegung", json={"menge": -4}, headers=hm).status_code == 409     # nicht unter null
    assert client.post(f"{V}/{t['id']}/bewegung", json={"menge": 0}, headers=hm).status_code == 400
    assert [x["bezeichnung"] for x in client.get(f"{API}/uebersicht", headers=hm).json()["nachbestellen"]] == ["Fügemesser 20 mm"]
    assert client.post(f"{V}/{t['id']}/bewegung", json={"menge": 10, "text": "Lieferung"}, headers=hm).json()["bestand"] == 13
    # Stammdaten ändern lässt den Bestand in Ruhe
    r = client.put(f"{V}/{t['id']}", json={"bezeichnung": "Fügemesser 20 mm HW", "bestand": 99, "mindestbestand": 2}, headers=h)
    assert (r.json()["bestand"], r.json()["mindestbestand"]) == (13, 2)
    assert len(client.get(V, headers=hm).json()) == 1
    assert client.delete(f"{V}/{t['id']}", headers=hm).status_code == 403
    assert client.delete(f"{V}/{t['id']}", headers=h).status_code == 204
    assert client.get(f"{V}/{t['id']}", headers=h).status_code == 404
