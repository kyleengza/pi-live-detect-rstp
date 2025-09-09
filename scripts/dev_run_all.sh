#!/usr/bin/env sh
set -e
. .venv/bin/activate || true
python -m app.main
