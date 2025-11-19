#!/bin/bash
export PATH="/root/.local/bin:$PATH:/app/.venv/bin"

echo "Starting Tor..."
tor &
sleep 15

echo "Starting Robin: AI-Powered Dark Web OSINT Tool..."
exec uv run robin "$@"