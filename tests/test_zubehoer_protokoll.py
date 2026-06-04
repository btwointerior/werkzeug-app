"""Tests für Zubehör-Mitnahme-Protokoll (To-Do Punkt 1)."""

from datetime import datetime, timezone

from backend.models import (
    Ausleihe,
    AusleiheZubehoer,
    Maschine,
    MaschinenStatus,
)

from .conftest import auth_header, make_user


def _maschine_mit_zubehoer(db, code="M-0001", teile=("Akku", "Ladegerät")):
    from backend.models import Zubehoer
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
