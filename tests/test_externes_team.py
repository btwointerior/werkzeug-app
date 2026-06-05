"""Tests für Ausleihen an externe Montageteams (To-Do Punkt 4)."""

from backend.models import (
    Ausleihe,
    ExternesTeam,
    Maschine,
    MaschinenStatus,
    Rolle,
)

from .conftest import auth_header, make_user


def _maschine(db, code="M-0001"):
    m = Maschine(maschinen_code=code, name="Bohrmaschine",
                 status=MaschinenStatus.VERFUEGBAR)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_modell_team_verknuepfung(db):
    user = make_user(db, "max")
    m = _maschine(db)
    ausleihe = Ausleihe(maschine_id=m.id, benutzer_id=user.id)
    ausleihe.externes_team = ExternesTeam(name="Team Müller")
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert ausleihe.externes_team_id is not None
    assert ausleihe.externes_team_name == "Team Müller"


def test_modell_ohne_team_ist_none(db):
    user = make_user(db, "max")
    m = _maschine(db)
    ausleihe = Ausleihe(maschine_id=m.id, benutzer_id=user.id)
    db.add(ausleihe)
    db.commit()
    db.refresh(ausleihe)

    assert ausleihe.externes_team_id is None
    assert ausleihe.externes_team_name is None


def test_ausleihen_fuer_mich_kein_team(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={}, headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(ExternesTeam).count() == 0
    assert db.query(Ausleihe).one().externes_team_id is None


def test_ausleihen_fuer_team_legt_team_an(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"externes_team": "Team Müller"},
                    headers=auth_header(user))

    assert r.status_code == 200
    team = db.query(ExternesTeam).one()
    assert team.name == "Team Müller"
    assert db.query(Ausleihe).one().externes_team_id == team.id


def test_ausleihen_gleicher_team_name_kein_duplikat(client, db):
    user = make_user(db, "max")
    m1 = _maschine(db, code="M-0001")
    m2 = _maschine(db, code="M-0002")

    for m in (m1, m2):
        r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                        json={"externes_team": "Team Müller"},
                        headers=auth_header(user))
        assert r.status_code == 200

    assert db.query(ExternesTeam).count() == 1
    team_ids = {a.externes_team_id for a in db.query(Ausleihe).all()}
    assert len(team_ids) == 1 and None not in team_ids


def test_ausleihen_team_whitespace_ist_fuer_mich(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"externes_team": "   "},
                    headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(ExternesTeam).count() == 0
    assert db.query(Ausleihe).one().externes_team_id is None


def test_ausleihen_ohne_feld_abwaertskompatibel(client, db):
    user = make_user(db, "max")
    m = _maschine(db)

    r = client.post(f"/api/maschinen/{m.id}/ausleihen",
                    json={"zubehoer_bezeichnungen": []},
                    headers=auth_header(user))

    assert r.status_code == 200
    assert db.query(Ausleihe).one().externes_team_id is None


def test_externe_teams_liste_distinct_sortiert(client, db):
    user = make_user(db, "max")
    m1 = _maschine(db, code="M-0001")
    m2 = _maschine(db, code="M-0002")
    client.post(f"/api/maschinen/{m1.id}/ausleihen",
                json={"externes_team": "Zeta-Bau"}, headers=auth_header(user))
    client.post(f"/api/maschinen/{m2.id}/ausleihen",
                json={"externes_team": "Alpha-Montage"}, headers=auth_header(user))

    r = client.get("/api/maschinen/externe-teams", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json() == ["Alpha-Montage", "Zeta-Bau"]


def test_externe_teams_leer(client, db):
    user = make_user(db, "max")

    r = client.get("/api/maschinen/externe-teams", headers=auth_header(user))

    assert r.status_code == 200
    assert r.json() == []
