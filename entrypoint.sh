#!/bin/bash

USER_ID=${HOST_UID:-1000}
GROUP_ID=${HOST_GID:-1000}

echo "Standardizing volume permissions to Host UID: $USER_ID and GID: $GROUP_ID..."

chown -R $USER_ID:$GROUP_ID /app/investigations

mkdir -p /app/tor_data
chown -R $USER_ID:$GROUP_ID /app/tor_data

echo "Starting Tor as UID $USER_ID..."
gosu $USER_ID:$GROUP_ID tor --DataDirectory /app/tor_data --SocksPort 127.0.0.1:9050 --CookieAuthentication 0 &

echo "Waiting for Tor proxy socket (127.0.0.1:9050)..."
timeout 60 bash -c '
until python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect((\"127.0.0.1\", 9050)); s.close()" 2>/dev/null; do
  sleep 2
done
'

if [ $? -ne 0 ]; then
  echo "ERROR: Tor failed to start."
  exit 1
fi

echo "Tor is ready."
echo "Starting Robin: AI-Powered Dark Web OSINT Tool as UID $USER_ID..."
exec gosu $USER_ID:$GROUP_ID env HOME=/app streamlit run ui.py --server.port=8501 --server.address=0.0.0.0