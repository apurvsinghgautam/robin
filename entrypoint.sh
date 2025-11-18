#!/bin/bash
set -euo pipefail

echo "Starting Tor..."
tor &

# Wait for Tor SOCKS to be ready (127.0.0.1:9050), up to ~60s
ATTEMPTS=0
until (echo > /dev/tcp/127.0.0.1/9050) 2>/dev/null; do
  ATTEMPTS=$((ATTEMPTS+1))
  if [ "$ATTEMPTS" -gt 60 ]; then
    echo "Tor did not become ready in time. Exiting."
    exit 1
  fi
  echo "Waiting for Tor SOCKS (9050)..."
  sleep 1
done

echo "Starting Robin: AI-Powered Dark Web OSINT Tool..."
exec python main.py "$@"
