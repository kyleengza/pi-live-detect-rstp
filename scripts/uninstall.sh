#!/usr/bin/env bash
set -euo pipefail
SERVICES=(pld_probe pld_detect pld_restream)
for s in "${SERVICES[@]}"; do
  sudo systemctl stop "$s" 2>/dev/null || true
  sudo systemctl disable "$s" 2>/dev/null || true
  sudo rm -f "/etc/systemd/system/${s}.service"
done
sudo systemctl daemon-reload
echo "Services removed. Data left intact."
