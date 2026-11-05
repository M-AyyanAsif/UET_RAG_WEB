# Security checklist and limitations

## Shipping protections

- Admin and Grafana passwords are randomized on initial install, stored in local `.env` with mode 600.
- API session cookie is HttpOnly, SameSite=Lax; API state changes require a custom same-origin CSRF guard header.
- Passwords use PBKDF2-HMAC-SHA256 with salt and 310,000 iterations.
- Admin-only endpoints protect uploads, KB management, user creation and document deletion. Each conversation belongs to its creator.
- Original files have UUID storage paths and no direct public mapping. Backend limits upload size and accepted file types.
- Ollama, Qdrant, Redis, Prometheus, backend and node exporter are not published as ECS public ports. Grafana is bound only to localhost.
- RAG prompt explicitly treats source documents as untrusted content, but model-level prompt injection protection cannot be guaranteed.

## Not implemented, and therefore not to be assumed

- HTTPS/TLS termination and production domain management. HTTP is for an isolated lab only. For internet-facing use, add HTTPS via trusted reverse proxy and set `COOKIE_SECURE=true`.
- Tenant-specific/KB-specific authorization: all members have access to all knowledge bases and downloadable documents. This is **not** suitable for multiple companies' private confidential documents.
- Enterprise IdP/SSO, MFA, advanced anti-brute-force protections, account lockout, user password reset UI, secure secret-manager integration, audit tamper resistance.
- Malware scanning or OCR of uploaded PDF documents. Only text-based content with normal PDF structure is handled.
- CloudEye / DRS / RDS / DCS service-specific telemetry integration. The included Prometheus dashboards show application, Qdrant and ECS host metrics.
- HA web tier: Docker on a single ECS remains a single point of failure even if managed RDS has an HA standby.
- Automatic migration of SQLite records to Huawei RDS, automatic RDS failback or cloud-level zero-downtime switching.
- Automatic file/SQL/Qdrant consistency reconciliation after partial failures.
- Kubernetes, horizontal autoscaling, CDN and comprehensive load testing.

## Practical operating rules

1. Permit inbound 8080 only from designated class networks and SSH 22 from trusted management IPs.
2. Back up uploads, SQL and Qdrant together. Replication and caching do not substitute for backups.
3. Limit model concurrency on 4 vCPU / 8 GB. Use small text files and restrict indexing load.
4. Do not publish secrets in screenshots or student course materials.
5. Give students only member accounts unless they need specific admin lab privileges.
6. Avoid destructive DR drills on shared data; use snapshot/test data and clearly documented rollback.
