#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
. "$REPO_ROOT/venv/bin/activate" && cd "$REPO_ROOT" && exec python src/restream.py >> "$REPO_ROOT/logs/restream.log" 2>&1
