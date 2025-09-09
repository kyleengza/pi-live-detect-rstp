#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
export API_TOKEN=${API_TOKEN:-changeme}
. "$REPO_ROOT/venv/bin/activate" && cd "$REPO_ROOT" && exec uvicorn src.pipeline.serve:app --host 0.0.0.0 --port 8000 >> "$REPO_ROOT/logs/api.log" 2>&1
