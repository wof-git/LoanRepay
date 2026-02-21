import os
import tempfile
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Set DATA_DIR before importing app modules
_tmpdir = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmpdir

from src.database import Base, get_db
from src.main import app


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_engine, db_session):
    """FastAPI test client with overridden DB dependency."""
    def override_get_db():
        session = sessionmaker(bind=db_engine)()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_loan_data():
    return {
        "name": "Test Loan",
        "principal": 30050.00,
        "annual_rate": 0.0575,
        "frequency": "fortnightly",
        "start_date": "2026-02-20",
        "loan_term": 52,
        "fixed_repayment": 612.39,
    }


@pytest.fixture
def created_loan(client, sample_loan_data):
    """Create a loan and return the response data."""
    res = client.post("/api/loans", json=sample_loan_data)
    assert res.status_code == 201
    return res.json()
