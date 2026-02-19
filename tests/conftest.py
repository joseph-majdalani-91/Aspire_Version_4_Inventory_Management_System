import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_ims.db"
os.environ["AUTH_PASSWORD_PEPPER"] = "test-pepper"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import run_seed  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_seed()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def manager_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "manager", "password": "manager123"},
    )
    assert response.status_code == 200
    return {"X-API-Key": response.json()["api_key"]}


@pytest.fixture
def viewer_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    )
    assert response.status_code == 200
    return {"X-API-Key": response.json()["api_key"]}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"X-API-Key": response.json()["api_key"]}
