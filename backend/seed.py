"""
Seed-Skript: legt Testdaten an, damit wir die App ausprobieren können.

Aufruf:  python -m backend.seed
"""

from backend.models import (
    init_db, SessionLocal,
    Benutzer, Maschine, Zubehoer, Rolle, MaschinenStatus,
)


def seed():
    init_db()
    db = SessionLocal()
    try:
        # bereits vorhandene Daten? -> abbrechen
        if db.query(Benutzer).first():
            print("Datenbank enthaelt bereits Daten - Seed uebersprungen.")
            return

        # ----- Benutzer -----
        admin = Benutzer(
            benutzername="admin",
            vorname="System",
            nachname="Administrator",
            rolle=Rolle.ADMIN,
            email="admin@firma.de",
        )
        admin.setze_passwort("admin123")  # !! beim ersten Login aendern

        max_m = Benutzer(
            benutzername="max.mueller",
            vorname="Max",
            nachname="Mueller",
            rolle=Rolle.MITARBEITER,
        )
        max_m.setze_passwort("test1234")

        anna = Benutzer(
            benutzername="anna.schmidt",
            vorname="Anna",
            nachname="Schmidt",
            rolle=Rolle.MITARBEITER,
        )
        anna.setze_passwort("test1234")

        db.add_all([admin, max_m, anna])

        # ----- Maschinen -----
        m1 = Maschine(
            maschinen_code="M-0001",
            name="Bohrmaschine Bosch GBH 18V",
            platznummer="A-12 / Regal 3",
            hersteller="Bosch Professional",
            seriennummer="BSH-2024-0142",
            beschreibung="Akku-Bohrhammer 18V mit SDS-Plus Aufnahme.",
            status=MaschinenStatus.VERFUEGBAR,
        )
        m1.zubehoer_liste = [
            Zubehoer(bezeichnung="2 Akkus 18V"),
            Zubehoer(bezeichnung="Ladegeraet"),
            Zubehoer(bezeichnung="Koffer"),
            Zubehoer(bezeichnung="Bohrer-Set"),
        ]

        m2 = Maschine(
            maschinen_code="M-0002",
            name="Winkelschleifer Makita GA9020",
            platznummer="B-04 / Regal 1",
            hersteller="Makita",
            seriennummer="MK-2023-8821",
            beschreibung="230 mm Winkelschleifer, 2200 Watt.",
            status=MaschinenStatus.VERFUEGBAR,
        )
        m2.zubehoer_liste = [
            Zubehoer(bezeichnung="Schutzhaube"),
            Zubehoer(bezeichnung="Zusatzhandgriff"),
            Zubehoer(bezeichnung="Spannschluessel"),
        ]

        m3 = Maschine(
            maschinen_code="M-0003",
            name="Stichsaege Festool PS 420",
            platznummer="A-08 / Regal 2",
            hersteller="Festool",
            seriennummer="FT-2024-1156",
            beschreibung="Pendelhubstichsaege mit Splitterschutz.",
            status=MaschinenStatus.WARTUNG,
        )

        db.add_all([m1, m2, m3])
        db.commit()

        print("Seed erfolgreich.")
        print(f"  - {db.query(Benutzer).count()} Benutzer angelegt")
        print(f"  - {db.query(Maschine).count()} Maschinen angelegt")
        print()
        print("Login-Daten:")
        print("  Admin       : admin       / admin123")
        print("  Mitarbeiter : max.mueller / test1234")
        print("  Mitarbeiter : anna.schmidt/ test1234")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
