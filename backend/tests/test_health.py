def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_status_degrades_cleanly(client):
    response = client.get("/api/v1/models/status")
    assert response.status_code == 200
    assert response.json()["reachable"] is False
    assert response.json()["capability_check"] == "offline_deterministic_fallback"
