#!/bin/sh
set -eu
# Mounted volumes can be root-owned. Only fix the designated data directory,
# then drop privileges before accepting requests.
mkdir -p /var/data
chown forma:forma /var/data
exec gosu forma python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
