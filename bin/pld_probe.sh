#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
export RUNTIME_DB=${RUNTIME_DB:-/dev/shm/pld_runtime.db}
echo "$(date): Health probe check" >> "$REPO_ROOT/logs/probe.log" 2>&1
curl -s http://localhost:8000/health >> "$REPO_ROOT/logs/probe.log" 2>&1 || echo "Service not available" >> "$REPO_ROOT/logs/probe.log" 2>&1
