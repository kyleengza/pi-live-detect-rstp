#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
echo "$(date): Restream service placeholder - WebRTC/MJPEG served by main API" >> "$REPO_ROOT/logs/restream.log" 2>&1
