"""API tests run without an actual Huawei account, Qdrant, Ollama or Redis server."""
import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# The packaging environment may not include redis-py; actual Docker image installs it.
try:
    import redis
except ImportError:
    redis = types.ModuleType("redis")
    class RedisError(Exception):
        pass
    class Redis:
        @staticmethod
        def from_url(*args, **kwargs):
            return Redis()
        def ping(self):
            raise RedisError("No Redis test server")
    redis.RedisError = RedisError
    redis.Redis = Redis
    sys.modules["redis"] = redis

_test_dir = tempfile.mkdtemp(prefix="cloudrag_test_")
os.environ["DATA_DIR"] = _test_dir
os.environ["SQLITE_PATH"] = str(Path(_test_dir) / "test.db")
os.environ["UPLOADS_DIR"] = str(Path(_test_dir) / "uploads")
os.environ["DB_MODE"] = "sqlite"
os.environ["RDS_HOST"] = ""
os.environ["REDIS_URL"] = ""
os.environ["ADMIN_EMAIL"] = "admin@kics.local"
os.environ["ADMIN_PASSWORD"] = "RandomAdminPassword12345!"
os.environ["SESSION_SECRET"] = "testing-session-secret-is-longer-than-32-characters"
