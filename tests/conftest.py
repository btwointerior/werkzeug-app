"""Test-Harness: isolierte In-Memory-SQLite-DB, kein Zugriff auf die echte DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import create_access_token
from backend.main import app
from backend.models import Base, Benutzer, Rolle, get_db


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Login-Drossel vor/nach jedem Test leeren (sonst leakt Zustand zwischen Tests)."""
    from backend import rate_limit

    rate_limit._reset_all()
    yield
    rate_limit._reset_all()


@pytest.fixture()
def db():
    """Frische In-Memory-DB pro Test (StaticPool -> eine geteilte Verbindung)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    """TestClient, dessen get_db auf die Test-DB zeigt."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---- Hilfsfunktionen ----

def make_user(db, benutzername, rolle=Rolle.MITARBEITER, aktiv=True, passwort="test1234"):
    u = Benutzer(
        benutzername=benutzername,
        vorname="Vor",
        nachname="Nach",
        rolle=rolle,
        aktiv=aktiv,
    )
    u.setze_passwort(passwort)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_header(user):
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}
