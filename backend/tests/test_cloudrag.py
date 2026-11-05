import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import services, db
from app.models import Document
from app.security import hash_password, verify_password


def test_password_hash_and_verify():
    hashed = hash_password("very-good-passphrase")
    assert hashed != "very-good-passphrase"
    assert verify_password("very-good-passphrase", hashed)
    assert not verify_password("not-my-password", hashed)


def test_document_chunking_is_bounded():
    text = ("Cloud storage stores files safely. Query indexes accelerate semantic retrieval. " * 70).strip()
    chunks = services.chunk_text(text, size=300, overlap=40)
    assert len(chunks) > 3
    assert all(0 < len(s) <= 300 for s in chunks)
    assert len(chunks) < 100


def test_extract_txt_and_markdown(tmp_path):
    sample = tmp_path / "policies.md"
    sample.write_text("## Annual leave\nAll employees have 20 working days.", encoding="utf-8")
    assert "20 working days" in services.extract_pages(sample, "policies.md")[0][1]
    with pytest.raises(ValueError):
        services.extract_pages(sample, "policies.exe")


def test_api_auth_sqlite_upload_and_rag(monkeypatch):
    # Simulate Ollama + Qdrant to test the complete API / SQL / file flow.
    indexed_points = []
    monkeypatch.setattr(services, "wait_for_embedding_model", lambda max_seconds=720: None)
    monkeypatch.setattr(services, "ollama_embed", lambda texts: [[0.4, 0.3, 0.2, 0.1] for _ in texts])
    monkeypatch.setattr(services, "ensure_qdrant_collection", lambda dimension: None)
    monkeypatch.setattr(services, "remove_document_vectors", lambda document_id: None)
    def fake_qdrant(method, path, payload=None, timeout=25):
        if "points?wait" in path:
            indexed_points.extend(payload["points"])
        return {"status": "ok", "result": {"points": []}}
    monkeypatch.setattr(services, "qdrant_request", fake_qdrant)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["database"] == "Local SQLite"
        assert client.get("/api/me").status_code == 401
        assert client.post("/api/knowledge-bases", json={"name":"Unauthorized"}).status_code == 403
        login = client.post("/api/login",json={"email":"admin@kics.local","password":"RandomAdminPassword12345!"})
        assert login.status_code == 200, login.text
        assert client.get("/api/me").json()["role"] == "admin"
        headers = {"X-CSRF-Guard":"cloudrag"}
        kb = client.get("/api/knowledge-bases").json()[0]
        doc_res=client.post("/api/documents/upload", headers=headers,
              data={"knowledge_base_id":kb["id"]}, files={"file":("test_policy.txt", b"Annual leave is 20 working days. CloudNova supports cloud migration and database reliability.", "text/plain")})
        assert doc_res.status_code == 202,doc_res.text
        doc = doc_res.json()
        assert doc["filename"] == "test_policy.txt"
        docs = client.get("/api/documents").json()
        assert docs[0]["state"] == "ready", docs
        assert docs[0]["chunk_count"] > 0
        assert len(indexed_points) > 0
        assert isinstance(indexed_points[0]["id"], str)
        assert client.get(f"/api/documents/{doc['id']}/download").status_code == 200
        assert client.post("/api/documents/upload", headers=headers,
             data={"knowledge_base_id":kb["id"]}, files={"file":("evil.exe",b"bad","application/octet-stream")}).status_code == 400
        # The no-source route avoids a mocked LLM network request but still stores query history.
        monkeypatch.setattr(services, "retrieve", lambda q,k,v: ([],False,0.01))
        resp=client.post("/api/chat/stream", headers=headers, json={"question":"What is the policy?","knowledge_base_id":kb["id"]})
        assert resp.status_code == 200,resp.text
        assert 'event: sources' in resp.text
        assert 'event: done' in resp.text
        assert 'cannot find supporting information' in resp.text
        analytics=client.get('/api/analytics').json()
        assert analytics['total_queries'] >= 1
        assert client.get('/api/dashboard').json()['indexed_documents'] >= 1
        assert client.post('/api/logout',headers=headers).status_code == 200
        assert client.get('/api/me').status_code == 401


def test_auto_rds_failure_uses_sqlite(monkeypatch):
    from app import config
    old_engine = db.engine
    old_session = db.SessionLocal
    monkeypatch.setattr(config, "DB_MODE", "auto")
    monkeypatch.setattr(config, "RDS_HOST", "127.0.0.1")
    # The simulated RDS address is deliberately unreachable.
    db.initialize()
    assert db.active_database == "Local SQLite"
    assert "RDS unreachable" in db.startup_warning
    # Restore original configuration for any subsequent tests.
    monkeypatch.setattr(config, "DB_MODE", "sqlite")
    monkeypatch.setattr(config, "RDS_HOST", "")
    db.initialize()
