import importlib.util

import pytest

HAS_API_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "sqlalchemy", "httpx"))


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", secret_key="test-secret-key-of-sufficient-length-123")
    with TestClient(create_app(settings)) as c:
        yield c


def login(client, role: str) -> dict:
    r = client.post(f"/api/auth/demo/{role}")
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def as_role(client):
    return lambda role: login(client, role)
