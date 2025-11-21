from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("ok", "degraded")
    assert "checks" in body

def test_predict_contract():
    r = client.post("/predict", json={"query": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert "prediction" in body
    assert "latency_ms" in body
    assert "model_version" in body
    assert "answer" in body["prediction"]
