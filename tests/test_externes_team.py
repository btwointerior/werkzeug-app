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
