#!/bin/bash
echo "Starting Tor..."
tor &
sleep 15

echo "Starting Robin: AI-Powered Dark Web OSINT Tool..."
exec python main.py "$@"