#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8030}"
FIXTURE="tests/fixtures/uci_iris.csv"
OUT="artifacts/live_data_analysis.json"

curl -fsS "$BASE_URL/health" > artifacts/live_data_health.json
curl -fsS -X POST "$BASE_URL/analyze-data" \
  -F "file=@${FIXTURE};type=text/csv" \
  -F "user_id=live-data-user" \
  -F "session_id=live-data-session" \
  > "$OUT"

printf '%s\n' '--- HEALTH ---'
cat artifacts/live_data_health.json
printf '\n%s\n' '--- ANALYSIS (key fields) ---'
grep -o '"mode":"[^"]*"\|"rows":[0-9]*\|"columns":[0-9]*\|"score":[0-9]*\|"status":"[^"]*"\|"headline":"[^"]*"' "$OUT" | head -n 12
