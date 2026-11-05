# SQL exercises

All SQL tables are created automatically at application boot (`Base.metadata.create_all`). The schema source is `backend/app/models.py`. This is adequate for the lab; use Alembic migrations for a production upgrade.

## Huawei RDS / DAS MySQL queries

```sql
SHOW DATABASES;
USE cloudrag;
SHOW TABLES;
DESCRIBE knowledge_bases;
DESCRIBE document_chunks;

SELECT name, updated_at FROM knowledge_bases ORDER BY updated_at DESC;
SELECT filename, state, chunk_count, indexed_at FROM documents ORDER BY created_at DESC;
SELECT role, COUNT(*) AS account_count FROM users GROUP BY role;
SELECT outcome, COUNT(*) AS query_count,
       ROUND(AVG(latency_ms), 0) AS avg_latency_ms
  FROM query_metrics GROUP BY outcome;
SELECT cache_hit, COUNT(*) AS query_count,
       ROUND(AVG(latency_ms), 0) AS avg_latency_ms
  FROM query_metrics GROUP BY cache_hit;
SELECT DATE(created_at) AS date, COUNT(*) AS questions
  FROM query_metrics GROUP BY DATE(created_at) ORDER BY date DESC;
SELECT s.title, m.role, LEFT(m.content, 140) AS content_excerpt
  FROM chat_sessions s JOIN chat_messages m ON s.id=m.session_id
  ORDER BY m.created_at DESC LIMIT 20;
```

## Local SQLite queries

Connect to the SQLite file safely from within the API container using the bundled Python sqlite3 module:

```bash
sudo docker compose exec -T api python - <<'PY'
import sqlite3
c = sqlite3.connect('/data/cloudrag.sqlite3')
for row in c.execute('SELECT name FROM sqlite_master WHERE type="table" ORDER BY name'):
    print(row[0])
for row in c.execute('SELECT outcome, COUNT(*), ROUND(AVG(latency_ms)) FROM query_metrics GROUP BY outcome'):
    print(row)
c.close()
PY
```

**Consistency note:** SQL contains metadata and the text chunks, but Qdrant holds vector indexes. Backup and recovery plans must include both stores and original upload files. When using MySQL on Huawei Cloud, don't assume a separate DRS target or read replica automatically protects local ECS volumes.
