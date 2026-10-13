import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.config import settings

# Create in-memory SQLite database engine for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = tmpdir
        yield
        settings.UPLOAD_DIR = orig_upload_dir

@pytest.fixture(scope="function")
def db():
    # Create the schema in SQLite
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def mock_celery_delay(monkeypatch):
    """
    Mock Celery's .delay() method to do nothing.
    """
    from app.tasks import process_csv_job
    calls = []
    
    def mock_delay(*args, **kwargs):
        calls.append((args, kwargs))
        return None
        
    monkeypatch.setattr(process_csv_job, "delay", mock_delay)
    return calls
