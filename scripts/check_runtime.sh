#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"

echo "Checking backend health: $API_BASE_URL"
curl -fsS "$API_BASE_URL/health" && echo

echo "Checking runtime health"
curl -fsS "$API_BASE_URL/runtime/health" && echo

echo "Checking local data safety"
curl -fsS "$API_BASE_URL/runtime/local-data" && echo

echo "Checking startup checklist"
curl -fsS "$API_BASE_URL/runtime/startup-checklist" && echo
