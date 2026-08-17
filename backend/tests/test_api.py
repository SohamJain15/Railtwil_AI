from fastapi.testclient import TestClient
from app.main import app

def test_health_and_empty_contracts():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/predictions").json()["status"] == "empty"
    assert len(client.get("/api/v1/platforms").json()["items"]) == 7
    scenario = client.get("/api/v1/scenarios/active").json()
    assert scenario["status"] == "available"
    assert scenario["events"][0]["target_id"]
    assert client.get("/api/v1/network").json()["edges"]
