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
