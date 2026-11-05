#!/usr/bin/env bash
# Consistent lab snapshot: downtime required. Do not use -v.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null; then echo 'Docker required'; exit 1; fi
DATE="$(date -u +%Y%m%d_%H%M%S)"
mkdir -p backups
ARCHIVE="$PWD/backups/cloudrag-lab-backup_$DATE.tar.gz"
printf 'Stopping services temporarily to snapshot all storage volumes...\n'
docker compose stop
restore(){ docker compose up -d >/dev/null 2>&1 || true; }
trap restore EXIT
# Alpine tar archiver runs with all volumes mounted read-only and uses no app dependencies.
docker run --rm \
 -v kics-cloudrag_api_data:/snapshot/api:ro \
 -v kics-cloudrag_qdrant_data:/snapshot/qdrant:ro \
 -v kics-cloudrag_ollama_data:/snapshot/ollama:ro \
 -v kics-cloudrag_redis_data:/snapshot/redis:ro \
 -v "$PWD/backups:/out" \
 alpine:3.21 tar czf "/out/$(basename "$ARCHIVE")" -C /snapshot .
chmod 600 "$ARCHIVE"
printf 'Saved %s\n' "$ARCHIVE"
printf 'Restarting services...\n'
