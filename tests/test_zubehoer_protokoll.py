"""Tests für Zubehör-Mitnahme-Protokoll (To-Do Punkt 1)."""

from datetime import datetime, timezone

from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Maschine,
    MaschinenStatus,
    Zubehoer,
)

from .conftest import auth_header, make_user


def _maschine_mit_zubehoer(db, code="M-0001", teile=("Akku", "Ladegerät")):
    m = Maschine(maschinen_code=code, name="Bohrmaschine",
                 status=MaschinenStatus.VERFUEGBAR)
    for t in teile:
        m.zubehoer_liste.append(Zubehoer(bezeichnung=t))
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_modell_speichert_und_cascade_loescht(db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db)
    ausleihe = Ausleihe(
        maschine_id=m.id,
        benutzer_id=user.id,
        ausleih_zeitpunkt=datetime.now(timezone.utc),
    )
    ausleihe.mitgenommenes_zubehoer.append(AusleiheZubehoer(bezeichnung="Akku"))
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert len(ausleihe.mitgenommenes_zubehoer) == 1
    zeile = ausleihe.mitgenommenes_zubehoer[0]
    assert zeile.bezeichnung == "Akku"
    assert zeile.zurueckgebracht is None

    # Cascade: Ausleihe löschen entfernt die Zubehör-Zeile
    db.delete(ausleihe)
    db.commit()
    assert db.query(AusleiheZubehoer).count() == 0


def test_ausleihen_speichert_angehakte_teile(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku", "Ladegerät", "Koffer"))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku", "Koffer"]},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeilen = db.query(AusleiheZubehoer).all()
    assert sorted(z.bezeichnung for z in zeilen) == ["Akku", "Koffer"]
    assert all(z.zurueckgebracht is None for z in zeilen)


def test_ausleihen_mit_leerer_liste(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db)

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": []},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    assert db.query(AusleiheZubehoer).count() == 0
    db.refresh(m)
    assert m.status == MaschinenStatus.AUSGELIEHEN


def test_ausleihen_unbekannte_bezeichnung_400(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku", "Phantom-Teil"]},
        headers=auth_header(user),
    )

    assert r.status_code == 400
    assert db.query(Ausleihe).count() == 0
    db.refresh(m)
    assert m.status == MaschinenStatus.VERFUEGBAR


def test_protokoll_ist_schnappschuss(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db, teile=("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": ["Akku"]},
        headers=auth_header(user),
    )
    assert r.status_code == 200

    # Admin entfernt das Zubehör der Maschine komplett
    db.query(Zubehoer).filter(Zubehoer.maschine_id == m.id).delete()
    db.commit()

    zeile = db.query(AusleiheZubehoer).one()
    assert zeile.bezeichnung == "Akku"  # Protokoll unverändert


def test_ausleihen_ohne_body_funktioniert(client, db):
    user = make_user(db, "max")
    m = _maschine_mit_zubehoer(db)
    r = client.post(f"/api/maschinen/{m.id}/ausleihen", headers=auth_header(user))
    assert r.status_code == 200
    assert db.query(AusleiheZubehoer).count() == 0


def _ausleihen_mit_zubehoer(client, db, user, teile, mitnehmen):
    m = _maschine_mit_zubehoer(db, teile=teile)
    r = client.post(
        f"/api/maschinen/{m.id}/ausleihen",
        json={"zubehoer_bezeichnungen": list(mitnehmen)},
        headers=auth_header(user),
    )
    assert r.status_code == 200
    return m


def test_rueckgabe_alles_zurueck(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku", "Ladegerät"), ("Akku", "Ladegerät"))
    ids = [z.id for z in db.query(AusleiheZubehoer).all()]

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": None,
              "zurueckgebrachte_zubehoer_ids": ids},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeilen = db.query(AusleiheZubehoer).all()
    assert all(z.zurueckgebracht is True for z in zeilen)
    ausleihe = db.query(Ausleihe).one()
    assert "Nicht zurückgegeben" not in (ausleihe.rueckgabe_kommentar or "")


def test_rueckgabe_mit_fehlendem_teil(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku", "Ladegerät"), ("Akku", "Ladegerät"))
    akku = db.query(AusleiheZubehoer).filter_by(bezeichnung="Akku").one()

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": "alles gut",
              "zurueckgebrachte_zubehoer_ids": [akku.id]},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    db.expire_all()
    akku = db.query(AusleiheZubehoer).filter_by(bezeichnung="Akku").one()
    lader = db.query(AusleiheZubehoer).filter_by(bezeichnung="Ladegerät").one()
    assert akku.zurueckgebracht is True
    assert lader.zurueckgebracht is False
    ausleihe = db.query(Ausleihe).one()
    assert "Ladegerät" in ausleihe.rueckgabe_kommentar
    assert "Nicht zurückgegeben" in ausleihe.rueckgabe_kommentar
    assert "alles gut" in ausleihe.rueckgabe_kommentar  # Originalkommentar bleibt


def test_rueckgabe_ohne_feld_abwaertskompatibel(client, db):
    user = make_user(db, "max")
    m = _ausleihen_mit_zubehoer(client, db, user, ("Akku",), ("Akku",))

    r = client.post(
        f"/api/maschinen/{m.id}/zurueckgeben",
        json={"zustand": "ok", "kommentar": None},
        headers=auth_header(user),
    )

    assert r.status_code == 200
    zeile = db.query(AusleiheZubehoer).one()
    assert zeile.zurueckgebracht is True
