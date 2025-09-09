# Contributing

## Development Setup
1. Run `scripts/install.sh install`
2. Copy `.env.example` to `.env` and adjust.
3. Run server: `python -m src.pipeline.serve`.

## Pre-commit
Install hooks:
```
pip install pre-commit
pre-commit install
```

## Coding Style
- Black + isort enforced.
- Flake8 (bugbear) for lint.
- Keep functions small & typed.

## Commits
Conventional style (examples):
- feat: add webrtc preview
- fix: handle rtsp reconnect
- chore: update deps
- refactor: split infer engine

## Issues
Open with clear reproduction & hardware context (Pi model, Hailo version, camera).
