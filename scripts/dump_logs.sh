#!/usr/bin/env bash
set -euo pipefail

OUT=${1:-/dev/stdout}
BASE_DIR=${BASE_DIR:-$(pwd)}
LOG_DIR=${LOG_DIR:-$BASE_DIR/logs}
DB_PATH=${DB_PATH:-$BASE_DIR/data/app.db}
STATUS_FILE=${STATUS_FILE:-$BASE_DIR/stream_status.json}
TAIL=${TAIL:-30}

for arg in "$@"; do
  case "$arg" in
    --tail=*) TAIL="${arg#*=}";;
  esac
done

# Only tee when OUT is not stdout to prevent duplicated lines
if [[ "$OUT" != "/dev/stdout" && "$OUT" != "-" ]]; then
  exec > >(tee "$OUT") 2>&1
fi

echo "=== dump_logs: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# Environment summary
echo "--- env ---"
printf 'LOG_LEVEL=%s\nLOG_FORMAT=%s\nLOG_ROTATE_MB=%s\nLOG_BACKUPS=%s\n' \
  "${LOG_LEVEL:-}" "${LOG_FORMAT:-}" "${LOG_ROTATE_MB:-}" "${LOG_BACKUPS:-}" || true

# Service statuses
for SVC in pld_probe pld_detect pld_restream; do
  echo "--- systemctl status $SVC (short) ---"
  systemctl is-active $SVC 2>/dev/null || true
  systemctl is-enabled $SVC 2>/dev/null || true
  echo
  echo "--- journal (last $TAIL) $SVC ---"
  journalctl -u $SVC -n "$TAIL" --no-pager 2>/dev/null | sed 's/\x1B\[[0-9;]*[A-Za-z]//g' || true
  echo
done

# Log files (rotating)
if [[ -d "$LOG_DIR" ]]; then
  echo "--- log directory listing ---"
  ls -1lh "$LOG_DIR" || true
  for f in "$LOG_DIR"/*.log; do
    [[ -f "$f" ]] || continue
    echo "--- tail($TAIL) $f ---"
    tail -n "$TAIL" "$f" | sed 's/\x1B\[[0-9;]*[A-Za-z]//g' || true
    echo
  done
fi

# Stream status
if [[ -f "$STATUS_FILE" ]]; then
  echo "--- stream_status.json ---"
  cat "$STATUS_FILE" || true
  echo
fi

# Database stats
if [[ -f "$DB_PATH" ]]; then
  echo "--- database counts ---"
  sqlite3 "$DB_PATH" 'SELECT "frames", COUNT(*) FROM frames;' 2>/dev/null || true
  sqlite3 "$DB_PATH" 'SELECT "detections", COUNT(*) FROM detections;' 2>/dev/null || true
  echo "--- last 5 frames ---"
  sqlite3 "$DB_PATH" 'SELECT id, substr(ts,1,19), width, height, fps FROM frames ORDER BY id DESC LIMIT 5;' 2>/dev/null || true
  echo "--- last 5 detections ---"
  sqlite3 "$DB_PATH" 'SELECT id, frame_id, class, round(conf,3) FROM detections ORDER BY id DESC LIMIT 5;' 2>/dev/null || true
fi

echo "=== end dump_logs ==="
