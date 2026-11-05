#!/usr/bin/env bash
set -Eeuo pipefail
URL="${1:-http://127.0.0.1:8080}"
echo "Testing $URL"
command -v curl >/dev/null || { echo 'curl required'; exit 1; }
curl -fsS "$URL/api/health" && echo
echo 'Web HTML:'
curl -fsS "$URL/" | grep -q 'KICS CloudRAG' && echo 'PASS'
echo 'Unauthenticated /api/me must return 401:'
STATUS="$(curl -s -o /dev/null -w '%{http_code}' "$URL/api/me")"
[[ "$STATUS" == '401' ]] || { echo "FAIL: got $STATUS"; exit 1; }
echo 'PASS: session authentication enforced'
echo 'Open the portal, log in, and load the demonstration documents.'
