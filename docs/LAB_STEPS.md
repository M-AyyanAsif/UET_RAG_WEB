# Student laboratory exercises — KICS CloudRAG

**Goal:** Build and operate a company AI knowledge assistant using Huawei ECS, Docker, AI inference, vector search, SQL, caching, and monitoring.

## Stage 1 — ECS + Docker + security groups

- Deploy Ubuntu 24.04 (4 vCPU / 8 GB) on ECS, attach EIP, allow SSH from instructor IP and TCP 8080 only from class IPs.
- Unzip source and run `sudo bash deploy.sh`.
- Verify `docker compose ps`, UI login and the `smoke-test.sh` checks.
- Evidence: diagram (VPC/subnet/SG/ECS), running service table, screenshot of portal.

## Stage 2 — SQLite + SQL / optional Huawei RDS

- Before RDS, demonstrate `/api/dashboard`, `/api/users`, SQLite file persistence.
- Upload demo documents; identify table purpose in `backend/app/models.py`.
- Optional Huawei Koolab: create RDS MySQL instance, create `cloudrag` database, allow 3306 only from ECS private network, set `.env`, recreate API.
- Evidence: table listing, SQL queries, successful private connectivity. **Warn: local data is not auto-migrated.**

## Stage 3 — Ollama + chunking + embeddings + Qdrant

- `docker compose exec ollama ollama list` shows `qwen3:1.7b` and `nomic-embed-text`.
- Load demo documents from the admin portal. Wait for `ready` states.
- Ask questions: annual leave, remote work, critical support acknowledgment, and a deliberately unanswerable question.
- Open citation cards, note exact filenames, scores and passage text.
- Evidence: 4 questions, screenshots of answers and retrieved snippets. Explain why the SQL database is NOT the vector store.

## Stage 4 — Huawei DCS Redis

- Ask a question, repeat exactly; Analytics should show retrieval cache hits. Use Grafana counter `cloudrag_retrieval_cache_hits_total`.
- Switch to Huawei DCS by setting a secure `REDIS_URL` and re-creating API, or use the included Redis service.
- Disable Redis by setting `REDIS_URL=` and observe the application continuing without cache.
- Evidence: two before/after retrieval-time measurements, cache hit count, note that model generation still occurs on each request.

## Stage 5 — RDS read replicas

- Create a read replica of primary RDS, grant read permissions, specify `RDS_REPLICA_HOST`.
- Ask queries; inspect Analytics `database_source` field and records.
- Discuss asynchronous replication lag, stale read tolerance, why write traffic must remain on primary.
- Evidence: replica connection indicator and SQL read experiment.

## Stage 6 — Huawei DRS replication and recovery

- Configure a separate RDS target using Huawei DRS full + incremental migration as taught by the original Koolab.
- Show existence/consistency of `users`, `chat_messages`, and `query_metrics` between source and target.
- Describe recovery steps and explain why DRS target is not the same as an HA standby or read replica.
- Evidence: DRS console task, record comparison, RPO/RTO discussion; **do not modify primary production-looking data**.

## Stage 7 — Monitoring and architecture stress test

- Open Grafana via SSH tunnel, view the `KICS CloudRAG` dashboard.
- Observe API traffic, p95 RAG latency, document uploads, host CPU and available memory.
- Run 5 questions sequentially; compare durations and note CPU contention.
- Do not unleash concurrent whole-class queries on the 8-GB ECS.
- Evidence: screenshots, bottleneck analysis, and a short report recommending the next scaling step (separate model server, stronger ECS, job queue, backup plan).

## Suggested acceptance exercise

Use 10 supported and 5 unsupported questions drawn from the demo documents. Mark whether the correct source appears in retrieved top-K, whether answer statements are supported, and whether unsupported questions were refused. Report retrieval success and unsupported-answer rate separately; do not invent a universal accuracy figure.
