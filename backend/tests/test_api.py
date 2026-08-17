from fastapi.testclient import TestClient
from app.main import app

def test_health_and_empty_contracts():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/predictions").json()["status"] == "empty"
    assert len(client.get("/api/v1/platforms").json()["items"]) == 7
