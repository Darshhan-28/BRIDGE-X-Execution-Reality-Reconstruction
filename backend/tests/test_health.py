from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "BRIDGE-X"
    assert body["database"] == "up"
    # P1 must survive without an API key
    assert body["llm"] in ("configured", "fallback-only")


def test_root_points_to_docs():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["health"] == "/api/health"
