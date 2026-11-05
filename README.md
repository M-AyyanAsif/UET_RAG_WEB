# KICS CloudRAG Enterprise Lab

**Self-hosted, document-grounded AI assistant on Huawei Cloud ECS**. Educational deployment for Ubuntu Server 24.04 LTS (x86_64). No external paid AI APIs and **no OBS service** are required.

## What is included

- React admin dashboard, document inventory, user accounts, chat interface with streaming AI responses and references to retrieved passages.
- Python FastAPI backend, session authentication, access roles, audit records, SQL analytics, application metrics.
- Local CPU-based Ollama AI (`qwen3:1.7b` and `nomic-embed-text`), Qdrant vector search and document text extraction for PDF / DOCX / TXT / MD.
- **Automatic SQLite fallback** when Huawei RDS is not configured or is unavailable. SQLite survives restarts in a Docker volume.
- Optional RDS MySQL 8.0 for structured data, optional read replica for reporting, optional Huawei DCS Redis for retrieval cache. A local Redis container works out of the box.
- Persistent **local uploads** on a Docker named volume. No OBS, S3, or external object storage.
- Prometheus, Grafana, node exporter with a ready dashboard. All credentials generated on first install.
- Sample **fictional** company documents to test the RAG workflow.

> This is a **training application** suitable for limited traffic, not an audited production deployment. It uses a shared knowledge-base access model for logged-in users. Do not upload sensitive customer documents or expose it publicly without HTTPS, stronger access controls, vulnerability review, backups and appropriate regulatory assessment.

## Hardware & prerequisites

| Item | Minimum starting point for lab |
| --- | --- |
| Huawei ECS | x86_64 Ubuntu 24.04, 4 vCPU / 8 GB RAM (CPU-only inference) |
| Disk | **at least 35 GB free** recommended, 50 GB preferred |
| EIP | Outbound internet required for image downloads, Python/npm dependencies, AI models |
| Firewall | Allow TCP **8080** from instructor/student IPs; SSH 22 from trusted IPs only |
| Cloud services | None mandatory beyond ECS: SQLite + local Redis + Qdrant work without RDS/DCS |

**Important:** 8 GB RAM is an intentionally constrained lab setting. `qwen3:1.7b` will be significantly slower than a GPU setup. Start with one active AI query, moderate-sized text documents, and do not run large-scale simultaneous load tests. Bandwidth does not accelerate CPU inference.

## One-command deployment

1. Transfer the ZIP to your ECS (`scp` or a browser upload) and unpack.
2. Enter the extracted folder:

```bash
cd KICS_CloudRAG_Enterprise_Lab
sudo bash deploy.sh
```

`deploy.sh` installs official Docker Engine/Compose packages if necessary, creates `.env` with **random credentials**, pulls container images, builds the web/backend images and launches services. The `model-init` container automatically downloads the two AI models. You can log in before model downloads finish, but indexing and AI chat need models ready.

The deployment script prints generated login credentials. They are retained in `.env` (mode 600). Store them safely.

Open the web app at:

```text
http://ECS_PUBLIC_IP:8080
```

Default **email** is `admin@kics.local`, and the **password is generated at deployment**. There is no shared default password.

**First exercise:** Log in → Knowledge Base → **Load two fictional company demo documents** → monitor indexing → AI Knowledge Chat → ask “What is the annual leave policy?” and examine the source citations.

### Track initialization

```bash
sudo docker compose ps
sudo docker compose logs -f model-init
sudo docker compose logs --tail=80 -f api
sudo docker compose logs --tail=80 ollama
sudo bash scripts/smoke-test.sh http://127.0.0.1:8080
```

You should see `model-init` exit with code `0` **after** both models are downloaded. An exited `model-init` is normal; it is a one-time setup job. The other services should remain running. If the model pull failed, retry with `sudo docker compose run --rm model-init`.

Do **not** run `docker compose down -v` unless you intentionally want to erase all uploaded data, models, vector indexes and monitoring state.

## Access Grafana securely

Grafana binds **only to ECS localhost:3000** so it is not exposed to the public internet. From your Windows PC PowerShell (with SSH credentials configured), run:

```powershell
ssh -L 3000:localhost:3000 ubuntu@ECS_PUBLIC_IP
```

Then visit `http://localhost:3000` on your PC. Username `admin`; password printed by `deploy.sh` and stored as `GRAFANA_PASSWORD` in `.env`. The `KICS CloudRAG` folder contains the dashboard; Prometheus is auto-provisioned.

Use your ECS image's actual SSH username: `ubuntu`, `root`, or the name assigned by your image.

## Optional: Huawei RDS MySQL 8.0

1. Ensure ECS and RDS are in the **same VPC/region** (AP-Singapore in the original Koolab diagram). In the RDS security group, allow inbound TCP 3306 **from the ECS security group / private IP**, not from `0.0.0.0/0`. Keep RDS off the public internet.
2. Create a database and least-privilege application login using the Huawei RDS DAS console or MySQL CLI. Example using an administrative account:

```sql
CREATE DATABASE IF NOT EXISTS cloudrag
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'cloudrag'@'%' IDENTIFIED BY 'YOUR_STRONG_RANDOM_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON cloudrag.* TO 'cloudrag'@'%';
```

3. Edit `.env`, replacing values with actual RDS credentials and floating/private endpoint. Restrict the user's connection origin using RDS networking/security controls.

```ini
DB_MODE=auto
RDS_HOST=192.168.2.100
RDS_PORT=3306
RDS_DATABASE=cloudrag
RDS_USER=cloudrag
RDS_PASSWORD=YOUR_STRONG_RANDOM_PASSWORD
RDS_REPLICA_HOST=
```

4. Restart **only the API service** and confirm the Infra page shows `RDS MySQL`:

```bash
sudo docker compose up -d --no-deps --force-recreate api
sudo docker compose logs --tail=80 api
```

**Fallback semantics:** `DB_MODE=auto` tries RDS at **startup only**. If RDS is absent/unreachable, it uses local SQLite and shows a warning in the dashboard. It does **not** live-switch during a running session. `DB_MODE=rds` instead refuses to start if RDS is unavailable (preferred to prevent split-brain in production). `DB_MODE=sqlite` always uses local SQLite.

**CRITICAL: SQLite data is NOT migrated automatically to MySQL.** If you start locally and later switch to RDS, the app uses a different data set. Export/import users, KBs, documents, chat histories and metadata deliberately before a database cutover. **Vector indexes and uploaded files are still on local volumes** and must stay consistent with the chosen SQL data set. Do not claim that simply setting `RDS_HOST` performs a migration.

**RDS read replica** (optional): Set `RDS_REPLICA_HOST` to the replica's private address and recreate API. Analytics SQL SELECT operations use it when connected. Replicas can exhibit lag, so chat writes and fresh session reads always use the primary. No read replica is needed for local SQLite.

## Optional: Huawei DCS Redis

The application includes a local Redis service with disk persistence. Set `REDIS_URL` to your Huawei DCS Redis endpoint when available, for example:

```ini
REDIS_URL=redis://:YOUR_DCS_PASSWORD@192.168.2.200:6379/0
```

Use `rediss://` if your DCS instance requires TLS, with appropriate certificate configuration. ECS and DCS must have approved private-network access and relevant security-group/whitelist rules.

```bash
sudo docker compose up -d --no-deps --force-recreate api
```

When Redis is unreachable, semantic retrieval still works but its **retrieval-result cache is bypassed**. This lab caches vector retrieval results for 10 minutes using a knowledge-base version marker; it does **not** blindly cache final AI responses. `REDIS_URL=` disables caching altogether.

## DRS and the secondary database

Huawei's Data Replication Service is managed outside Docker; **the app cannot create or monitor a DRS migration job**. Use the Huawei Console Koolab exercise to create a separate target RDS DB, configure full + incremental synchronization, and validate records across source and destination. It is not the same as a managed RDS HA standby or a read replica.

## Local persistence and backup

Docker named volumes:

| Volume | Contents |
| --- | --- |
| `kics-cloudrag_api_data` | `/data/cloudrag.sqlite3`, `/data/uploads/` documents |
| `kics-cloudrag_qdrant_data` | Vector collections and indexes |
| `kics-cloudrag_ollama_data` | Downloaded AI models |
| `kics-cloudrag_redis_data` | Local Redis append-only persistence |
| `kics-cloudrag_grafana_data` | Grafana state |
| `kics-cloudrag_prometheus_data` | Short-retention time series |

For a consistent teaching-lab snapshot, pause upload/queries and run `sudo bash scripts/backup.sh`. The script stops the services temporarily, archives the volumes, and restarts. It avoids taking inconsistent live SQLite/Qdrant copies. Store backups separately from the ECS for real recovery protection. If using Huawei RDS, also take an RDS snapshot/backup: the volume archive does **not** contain the managed MySQL database.

## Common operations

```bash
sudo docker compose ps
sudo docker compose restart api web
sudo docker compose logs -f api
sudo docker compose logs -f ollama
sudo docker compose exec ollama ollama list
sudo docker compose exec ollama ollama pull qwen3:1.7b
sudo docker compose exec api python -c 'from app import db; print(db.active_database)'
sudo docker compose down               # stops containers, retains ALL volumes
sudo docker compose up -d              # resumes
```

### Troubleshooting

- **Chat says model unavailable:** `docker compose logs model-init` and `docker compose exec ollama ollama list`. Re-pull missing models. Ensure outbound networking and enough disk.
- **Document says failed:** Click **Retry** after resolving the cause. An unencrypted, selectable-text PDF is required; scanned PDFs are rejected because no OCR is installed.
- **“No supporting information”:** Check the document state is `ready` and the chat's selected KB matches. Vector retrieval is not guaranteed correct for every question: use evaluation examples.
- **RDS unreachable:** Confirm VPC/SG/private address and database creation. Auto mode falls back to SQLite. Avoid silently mixing data across modes.
- **Slow answers:** CPU models often require tens of seconds; limit concurrent users. Check Grafana host CPU/RAM and API timings. Consider a larger ECS or an inference-only instance.
- **Web UI unreachable:** Check ECS security group TCP 8080, `docker compose ps`, `docker compose logs web` and your public IP/EIP. Do not expose port 11434, 6333, 6379, 3306 or 9090 publicly.
- **HTTP 502:** Usually backend initial startup/restart; check `docker compose logs api` and database configuration. Web service waits for API health on Compose startup.
- **Can't login:** The initial password in `.env` is only used when the admin account is first created; changing `.env` later does **not** reset an existing account.

## Files and teaching sequence

- `docs/ARCHITECTURE.md` — roles and data flows
- `docs/LAB_STEPS.md` — seven-stage student assignment and expected evidence
- `docs/SQL_EXPERIMENTS.md` — MySQL/SQLite queries and replica/DRS discussion
- `docs/SECURITY_AND_LIMITATIONS.md` — threat model, reliability, upgrade needs
- `backend/tests/` — code-level checks (run with pytest in a Python environment with the backend requirements)
- `TEST_RESULTS.md` — checks completed and live-deployment checks still required

## Service connection table

| Service | Connection | Notes |
| --- | --- | --- |
| Web | Public ECS `:8080` | Expose **only** to trusted IPs |
| FastAPI | Internal `api:8000` | Proxied under `/api/` |
| Ollama | Internal `ollama:11434` | Local models only |
| Qdrant | Internal `qdrant:6333` | Vector indexes |
| Local Redis | Internal `redis:6379` | Optional; bypass on failure |
| SQLite | Internal `/data/cloudrag.sqlite3` | Default automatic fallback |
| Huawei RDS | Private endpoint `:3306` | Optional SQL system of record |
| Huawei DCS | Private endpoint `:6379` or TLS port | Optional Redis cache |
| Prometheus | Internal `prometheus:9090` | 3-day TSDB retention |
| Grafana | `localhost:3000` on ECS | Access via SSH tunnel |

This is version 1.0 of the classroom lab. It intentionally favors a transparent architecture over feature-bloated third-party frameworks.
