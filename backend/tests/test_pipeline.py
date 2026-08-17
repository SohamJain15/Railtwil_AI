import time
from fastapi.testclient import TestClient
from app.main import app

def test_end_to_end_seeded_pipeline():
    client = TestClient(app)
    client.post("/api/v1/simulation/reset")
    started = client.post("/api/v1/simulation/start").json()
    assert started["simulation_id"]
    scenario = client.get("/api/v1/scenarios/active").json()
    event = scenario["events"][0]
    response = client.post("/api/v1/simulation/event", json={"event_type":"TRAIN_DELAY", **event, "scenario_id":scenario["scenario_id"]})
    assert response.status_code == 200
    assert client.post("/api/v1/predictions/run").status_code == 200
    assert client.post("/api/v1/conflicts/detect").status_code == 200
    recommendation = client.post("/api/v1/optimization/run").json()
    assert recommendation["recommendation_id"]
    decision = client.post(f"/api/v1/recommendations/{recommendation['recommendation_id']}/reject", json={"reason":"integration test"})
    assert decision.status_code == 200
    client.post("/api/v1/simulation/reset")
