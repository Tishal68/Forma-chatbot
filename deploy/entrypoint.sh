#!/bin/sh
set -eu
mkdir -p /var/data/attachments 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
    chown -R forma:forma /var/data 2>/dev/null || true
    exec gosu forma python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
else
    exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
fi
