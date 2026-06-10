#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"

echo "AI Private Workspace runtime troubleshooting"
echo "API: ${API_BASE_URL}"
echo

echo "1) Backend health"
curl -sS "${API_BASE_URL}/health" || true
echo

echo "2) Runtime health"
curl -sS "${API_BASE_URL}/runtime/health" || true
echo

echo "3) Runtime troubleshooting"
curl -sS "${API_BASE_URL}/runtime/troubleshooting" || true
echo

echo "4) Local data diagnostics"
curl -sS "${API_BASE_URL}/runtime/local-data" || true
echo

echo "This script only reads diagnostics endpoints. It does not start services, change config, or modify local data."
