#!/usr/bin/env sh
# No 'set -e' to keep going even if some steps fail.

if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=""; fi

printf "hailortcli version: "; hailortcli --version 2>/dev/null || echo "not found"

printf "\nPCI devices (Hailo):\n"
lspci -nn | grep -i hailo || echo "No Hailo device in lspci (ok if using USB variant)"

printf "\nHailo device scan (best-effort):\n"
hailortcli scan 2>/dev/null || hailortcli devices 2>/dev/null || hailortcli fw-control info 2>/dev/null || echo "Could not query device; driver/runtime may be missing."

printf "\nKernel modules (hailo):\n"
lsmod | grep -i hailo || echo "No hailo kernel module listed (ok for USB variant or if driver is not loaded yet)"
