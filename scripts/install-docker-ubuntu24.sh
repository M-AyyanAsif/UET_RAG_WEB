#!/usr/bin/env bash
set -Eeuo pipefail
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo 'Docker Engine and Compose v2 are already installed.'
  exit 0
fi
if [[ $(id -u) -ne 0 ]]; then echo 'Run this script using sudo/root.' >&2; exit 1; fi
. /etc/os-release
if [[ "${ID:-}" != 'ubuntu' || "${VERSION_ID:-}" != '24.04' ]]; then
  echo "WARNING: optimized for Ubuntu 24.04 (detected ${PRETTY_NAME:-unknown})." >&2
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
ARCH="$(dpkg --print-architecture)"
CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-noble}}"
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$ARCH" "$CODENAME" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker compose version
