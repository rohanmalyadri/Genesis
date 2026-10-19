import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.config import Settings, settings
from app.middleware import ApiGuardMiddleware


# ---- config -------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("*", ["*"]),
    ("http://a.com, http://b.com", ["http://a.com", "http://b.com"]),
    ('["http://a.com"]', ["http://a.com"]),
])
def test_allowed_hosts_accepts_star_csv_and_json(monkeypatch, raw, expected):
    monkeypatch.setenv("ALLOWED_HOSTS", raw)
    assert Settings(_env_file=None).ALLOWED_HOSTS == expected


def test_project_is_named_genesis_rag():
    assert Settings(_env_file=None).PROJECT_NAME == "Genesis RAG"


# ---- API key + rate limit middleware -----------------------------------------------

def _guarded_app():
    app = FastAPI()
    app.add_middleware(ApiGuardMiddleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return TestClient(app)


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret")
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 0)
    client = _guarded_app()
    assert client.get("/api/ping").status_code == 401
    assert client.get("/api/ping", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/ping", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/health").status_code == 200  # non-API paths stay open


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", None)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 3)
    client = _guarded_app()
    codes = [client.get("/api/ping").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


# ---- upload endpoint ---------------------------------------------------------------

@pytest.fixture
def upload_client(monkeypatch):
    from app.main import app
    from routes import ingest
    monkeypatch.setattr(settings, "API_KEY", None)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 0)
    seen = {}

    async def fake_process(path, **kwargs):
        seen.update(kwargs)
        return {"status": "indexed", "document_id": kwargs["original_name"], "chunks": 2, "graph": None}

    monkeypatch.setattr(ingest.ingest_pipeline, "process_file", fake_process)
    client = TestClient(app)
    client.seen = seen
    return client


def test_upload_rejects_unsupported_extension(upload_client):
    r = upload_client.post("/api/v1/ingest/", files={"file": ("virus.exe", b"x")})
    assert r.status_code == 415


def test_upload_strips_directory_parts_from_filename(upload_client):
    r = upload_client.post("/api/v1/ingest/", files={"file": ("../../etc/evil.txt", b"hello")})
    assert r.status_code == 200
    assert r.json()["filename"] == "evil.txt"
    assert upload_client.seen["original_name"] == "evil.txt"


def test_upload_enforces_size_limit(upload_client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    big = io.BytesIO(b"a" * (1024 * 1024 + 10))
    r = upload_client.post("/api/v1/ingest/", files={"file": ("big.txt", big)})
    assert r.status_code == 413


def test_upload_passes_options_through(upload_client):
    r = upload_client.post(
        "/api/v1/ingest/",
        files={"file": ("a.txt", b"hello")},
        data={"use_sharding": "false", "chunk_size": "256"},
    )
    assert r.status_code == 200 and r.json()["chunks"] == 2
    assert upload_client.seen["use_sharding"] is False
    assert upload_client.seen["chunk_size"] == 256
