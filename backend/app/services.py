"""Document extraction, Ollama embeddings/generation and Qdrant retrieval."""
import hashlib
import io
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any
import httpx
import redis
from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy import select, delete
from . import config, db
from .models import Document, DocumentChunk, KnowledgeBase, utcnow

log = logging.getLogger("cloudrag.services")
index_lock = threading.Lock()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP if overlap is None else overlap
    if size < 100 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be >=100; overlap must be smaller than chunk size")
    chunks = []
    text = normalize_text(text)
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            split = text.rfind("\n", start + size // 2, end)
            if split < 0:
                split = text.rfind(" ", start + size // 2, end)
            if split > start:
                end = split + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        start = next_start
    return chunks


def extract_pages(file_path: Path, filename: str) -> list[tuple[int | None, str]]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        if len(reader.pages) > 150:
            raise ValueError("PDF exceeds the 150-page lab limit")
        pages = [(i + 1, normalize_text(page.extract_text() or "")) for i, page in enumerate(reader.pages)]
    elif ext == ".docx":
        doc = DocxDocument(str(file_path))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append(" | ".join(cell.text for cell in row.cells))
        pages = [(None, normalize_text("\n".join(lines)))]
    elif ext in {".txt", ".md"}:
        raw = file_path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("Text files must be UTF-8 encoded")
        pages = [(None, normalize_text(text))]
    else:
        raise ValueError("Supported formats: PDF, DOCX, TXT and Markdown")
    total = sum(len(txt) for _, txt in pages)
    if not total:
        raise ValueError("No selectable text found; scanned PDFs require OCR, which is not part of this lab")
    if total > config.MAX_TEXT_CHARS:
        raise ValueError(f"Document exceeds the lab text limit ({config.MAX_TEXT_CHARS:,} characters)")
    return [(p, txt) for p, txt in pages if txt]


def cache_client():
    if not config.REDIS_URL:
        return None
    try:
        r = redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
        r.ping()
        return r
    except (redis.RedisError, ValueError, OSError):
        return None


def ollama_embed(texts: list[str]) -> list[list[float]]:
    with httpx.Client(timeout=httpx.Timeout(180, connect=5)) as client:
        response = client.post(f"{config.OLLAMA_URL}/api/embed", json={"model": config.EMBED_MODEL, "input": texts, "truncate": True})
        response.raise_for_status()
        vectors = response.json().get("embeddings", [])
    if len(vectors) != len(texts) or not all(vectors):
        raise RuntimeError("Unexpected embedding response from Ollama")
    return vectors


def qdrant_request(method: str, path: str, payload: dict | None = None, timeout: int = 25) -> dict:
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=3)) as client:
        response = client.request(method, f"{config.QDRANT_URL}{path}", json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("status") not in ("ok", None):
            raise RuntimeError(f"Qdrant status: {data.get('status')}")
        return data


def ensure_qdrant_collection(vector_size: int):
    path = f"/collections/{config.QDRANT_COLLECTION}"
    with httpx.Client(timeout=8) as client:
        res = client.get(f"{config.QDRANT_URL}{path}")
        if res.status_code == 404:
            qdrant_request("PUT", path, {"vectors": {"size": vector_size, "distance": "Cosine"}}, timeout=45)
            try:
                qdrant_request("PUT", f"{path}/index?wait=true", {"field_name": "knowledge_base_id", "field_schema": "keyword"})
            except Exception as exc:
                log.warning("Qdrant payload index not created: %s", exc)
        else:
            res.raise_for_status()
            existing = res.json().get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            dim = existing.get("size") if isinstance(existing, dict) else None
            if dim and dim != vector_size:
                raise RuntimeError(f"Existing Qdrant collection uses {dim}-dimension vectors; model returned {vector_size}. Reset collection or restore original embedding model.")


def remove_document_vectors(document_id: str):
    try:
        qdrant_request("POST", f"/collections/{config.QDRANT_COLLECTION}/points/delete?wait=true",
            {"filter": {"must": [{"key": "document_id", "match": {"value": document_id}}]}})
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise


def wait_for_embedding_model(max_seconds: int = 720):
    """Newly deployed servers need time to download models before ingestion."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        online, models = model_status()
        wanted = config.EMBED_MODEL
        if online and (wanted in models or f"{wanted}:latest" in models):
            return
        time.sleep(10)
    raise RuntimeError("Ollama embedding model is not ready. Check: docker compose logs model-init")


def index_document(document_id: str):
    # A single worker prevents 4-vCPU lab servers from being overwhelmed by simultaneous indexing.
    with index_lock:
        with db.SessionLocal() as session:
            doc = session.get(Document, document_id)
            if not doc or doc.state == "deleted":
                return
            doc.state = "processing"
            doc.error = ""
            session.commit()
            filename = doc.filename
            filepath = config.UPLOADS_DIR / doc.stored_filename
            kb_id = doc.knowledge_base_id
        try:
            pages = extract_pages(filepath, filename)
            parts = [(page, text) for page, full_text in pages for text in chunk_text(full_text)]
            if len(parts) > config.MAX_CHUNKS:
                raise ValueError(f"Too many chunks ({len(parts)}); max {config.MAX_CHUNKS} per document")
            wait_for_embedding_model()
            vectors = []
            # Avoid overloading Ollama: short batches, one at a time.
            for i in range(0, len(parts), 8):
                vectors.extend(ollama_embed([text for _, text in parts[i:i+8]]))
            ensure_qdrant_collection(len(vectors[0]))
            # Remove prior failed/partial indexing before idempotent re-index.
            remove_document_vectors(document_id)
            chunks = []
            for i, ((page, text), vector) in enumerate(zip(parts, vectors)):
                chunk = DocumentChunk(id=str(uuid.uuid4()), document_id=document_id, knowledge_base_id=kb_id, ordinal=i + 1,
                                      page=page, text=text)
                chunks.append((chunk, vector))
            for i in range(0, len(chunks), 32):
                batch = chunks[i:i+32]
                points = [{"id": c.id, "vector": v, "payload": {"document_id": document_id,
                          "knowledge_base_id": kb_id, "chunk_id": c.id, "filename": filename,
                          "page": c.page, "ordinal": c.ordinal, "text": c.text}}
                          for c, v in batch]
                qdrant_request("PUT", f"/collections/{config.QDRANT_COLLECTION}/points?wait=true", {"points": points}, timeout=90)
            with db.SessionLocal() as session:
                session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
                session.add_all([c for c, _ in chunks])
                doc = session.get(Document, document_id)
                if doc:
                    doc.state = "ready"
                    doc.chunk_count = len(chunks)
                    doc.indexed_at = utcnow()
                    kb = session.get(KnowledgeBase, kb_id)
                    if kb:
                        kb.updated_at = utcnow()
                session.commit()
            log.info("Indexed %s (%s chunks)", filename, len(chunks))
        except Exception as exc:
            log.exception("Index failed for document %s", document_id)
            with db.SessionLocal() as session:
                doc = session.get(Document, document_id)
                if doc:
                    doc.state = "failed"
                    doc.error = f"{type(exc).__name__}: {str(exc)[:420]}"
                    session.commit()


def retrieve(question: str, kb_id: str, kb_version: str) -> tuple[list[dict[str, Any]], bool, float]:
    started = time.monotonic()
    r = cache_client()
    fingerprint = hashlib.sha256(f"{kb_id}:{kb_version}:{config.EMBED_MODEL}:{question.strip().lower()}".encode()).hexdigest()
    key = f"cloudrag:retrieval:{fingerprint}"
    if r is not None:
        try:
            cached = r.get(key)
            if cached:
                return json.loads(cached), True, time.monotonic() - started
        except redis.RedisError:
            pass
    vector = ollama_embed([question])[0]
    ensure_qdrant_collection(len(vector))
    result = qdrant_request("POST", f"/collections/{config.QDRANT_COLLECTION}/points/query", {
        "query": vector,
        "filter": {"must": [{"key": "knowledge_base_id", "match": {"value": kb_id}}]},
        "limit": config.TOP_K, "with_payload": True, "with_vector": False,
    })
    points = result.get("result", {}).get("points", [])
    sources = []
    for p in points:
        payload = p.get("payload", {})
        sources.append({"document_id": payload.get("document_id"), "filename": payload.get("filename"),
                        "page": payload.get("page"), "ordinal": payload.get("ordinal"),
                        "score": round(float(p.get("score", 0)), 4),
                        "excerpt": payload.get("text", "")[:1600]})
    if r is not None:
        try:
            r.setex(key, 600, json.dumps(sources))
        except redis.RedisError:
            pass
    return sources, False, time.monotonic() - started


def model_status():
    try:
        with httpx.Client(timeout=3) as client:
            res = client.get(f"{config.OLLAMA_URL}/api/tags")
            res.raise_for_status()
            return True, [m.get("name") for m in res.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return False, []


def infra_status():
    from sqlalchemy import text as sql_text
    status = {"database": db.active_database, "db_warning": db.startup_warning, "replica_configured": bool(config.RDS_REPLICA_HOST),
              "replica_active": db.replica_engine is not None, "rds_configured": bool(config.RDS_HOST),
              "storage": "Persistent local Docker volume /data/uploads", "redis": False, "qdrant": False,
              "ollama": False, "models": [], "chat_model": config.CHAT_MODEL, "embed_model": config.EMBED_MODEL,
              "drs": "Configure in Huawei Cloud Console (external to application)"}
    status["redis"] = cache_client() is not None
    status["ollama"], status["models"] = model_status()
    try:
        with httpx.Client(timeout=3) as client:
            result = client.get(f"{config.QDRANT_URL}/healthz")
            status["qdrant"] = result.status_code == 200
    except httpx.HTTPError:
        pass
    return status
