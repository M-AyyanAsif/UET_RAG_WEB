import os
from pathlib import Path


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DATA_DIR = Path(get("DATA_DIR", "/data"))
UPLOADS_DIR = Path(get("UPLOADS_DIR", str(DATA_DIR / "uploads")))
SQLITE_PATH = Path(get("SQLITE_PATH", str(DATA_DIR / "cloudrag.sqlite3")))
DB_MODE = get("DB_MODE", "auto").strip().lower()
RDS_HOST = get("RDS_HOST")
RDS_PORT = int(get("RDS_PORT", "3306"))
RDS_DATABASE = get("RDS_DATABASE", "cloudrag")
RDS_USER = get("RDS_USER", "cloudrag")
RDS_PASSWORD = get("RDS_PASSWORD")
RDS_REPLICA_HOST = get("RDS_REPLICA_HOST")
ADMIN_EMAIL = get("ADMIN_EMAIL", "admin@kics.local").lower()
ADMIN_PASSWORD = get("ADMIN_PASSWORD", "")
SESSION_SECRET = get("SESSION_SECRET", "")
COOKIE_SECURE = get("COOKIE_SECURE", "false").lower() == "true"
OLLAMA_URL = get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
QDRANT_URL = get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
QDRANT_COLLECTION = get("QDRANT_COLLECTION", "cloudrag_chunks")
REDIS_URL = get("REDIS_URL", "redis://redis:6379/0")
CHAT_MODEL = get("CHAT_MODEL", "qwen3:1.7b")
EMBED_MODEL = get("EMBED_MODEL", "nomic-embed-text")
MAX_UPLOAD_MB = int(get("MAX_UPLOAD_MB", "15"))
MAX_TEXT_CHARS = int(get("MAX_TEXT_CHARS", "250000"))
MAX_CHUNKS = int(get("MAX_CHUNKS", "250"))
CHUNK_SIZE = int(get("CHUNK_SIZE", "950"))
CHUNK_OVERLAP = int(get("CHUNK_OVERLAP", "150"))
TOP_K = int(get("TOP_K", "4"))
MAX_CONTEXT_CHARS = int(get("MAX_CONTEXT_CHARS", "6500"))
MAX_GENERATION_TOKENS = int(get("MAX_GENERATION_TOKENS", "280"))
