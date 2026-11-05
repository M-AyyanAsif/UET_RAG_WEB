#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
umask 077
printf '\n=== KICS CloudRAG | Ubuntu 24.04 ECS Deployment ===\n'
if [[ ! -f .env ]]; then
  if ! command -v python3 >/dev/null 2>&1; then echo 'Python 3 is needed to generate secure credentials.' >&2; exit 1; fi
  python3 - <<'PY'
import secrets
from pathlib import Path
s = Path('.env.example').read_text()
s = s.replace('REPLACE_WITH_RANDOM_24_CHARACTER_PASSWORD', secrets.token_urlsafe(20))
s = s.replace('REPLACE_WITH_RANDOM_64_CHARACTER_SESSION_SECRET', secrets.token_urlsafe(48))
s = s.replace('REPLACE_WITH_RANDOM_PASSWORD', secrets.token_urlsafe(20))
Path('.env').write_text(s)
PY
  chmod 600 .env
  echo 'Created .env with random admin, session and Grafana passwords.'
else
  echo 'Keeping your existing .env configuration and passwords.'
fi
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo 'Docker Compose v2 is missing; installing official Docker packages...'
  if [[ $(id -u) -ne 0 ]]; then
    echo 'Run: sudo bash deploy.sh' >&2; exit 1
  fi
  bash scripts/install-docker-ubuntu24.sh
fi
if ! docker info >/dev/null 2>&1; then
  if [[ $(id -u) -ne 0 ]]; then echo 'Cannot access Docker daemon. Run: sudo bash deploy.sh' >&2; exit 1; fi
  systemctl enable --now docker
fi
echo 'Validating Docker Compose configuration...'
docker compose config --quiet
echo 'Pulling images and building the application...'
docker compose pull --ignore-buildable
docker compose up --build -d --remove-orphans
printf '\n=== Deployment initiated ===\n'
printf 'Web portal: http://ECS_PUBLIC_IP:%s\n' "$(sed -n 's/^APP_PORT=//p' .env | head -1)"
printf 'Login email: %s\n' "$(sed -n 's/^ADMIN_EMAIL=//p' .env | head -1)"
printf 'Login password: %s\n' "$(sed -n 's/^ADMIN_PASSWORD=//p' .env | head -1)"
printf 'Grafana password: %s\n' "$(sed -n 's/^GRAFANA_PASSWORD=//p' .env | head -1)"
printf '\nAI models download automatically (can take several minutes).\n'
printf 'Monitor downloads: sudo docker compose logs -f model-init\n'
printf 'Check services:    sudo docker compose ps\n'
printf 'Grafana tunnel:    ssh -L 3000:localhost:3000 ubuntu@ECS_PUBLIC_IP\n'
printf 'IMPORTANT: limit access to TCP 8080 at the Huawei security group.\n'
printf 'See README.md for configuration, test cases and maintenance.\n\n'
