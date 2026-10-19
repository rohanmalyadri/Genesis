from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "Genesis RAG" in body["message"]
    assert "Obscuron X Labs" in body["made_by"]


def test_health_check_reports_every_dependency():
    response = client.get("/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Genesis RAG"
    for key in ("status", "chroma", "redis", "neo4j", "model"):
        assert key in body
