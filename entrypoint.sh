#!/bin/bash

# One image, two front doors: `ui` (the default) serves Streamlit on 8501 and
# `mcp` serves MCP on stdio. In `mcp` mode stdout is the JSON-RPC transport and
# one stray line breaks it for every host, so all other output goes to stderr.

# Tor opens its SOCKS port before it can build circuits, and a search in that
# window reaches far fewer engines. Its notices go to a file so Robin can tell
# the two apart; an unwritable HOME leaves the path empty and only the port counts.
export ROBIN_TOR_LOG="${ROBIN_TOR_LOG:-$HOME/tor-notices.log}"
: > "$ROBIN_TOR_LOG" 2>/dev/null || export ROBIN_TOR_LOG=""
tor_with_log() {
  if [ -n "$ROBIN_TOR_LOG" ]; then
    tor --Log "notice file $ROBIN_TOR_LOG"
  else
    tor
  fi
}

wait_for_bootstrap() {
  # Returns 1 if it never reported in; the caller decides what that means.
  [ -n "$ROBIN_TOR_LOG" ] || return 0
  timeout "${1:-120}" bash -c '
    until grep -q "Bootstrapped 100%" "$0" 2>/dev/null; do sleep 2; done
  ' "$ROBIN_TOR_LOG"
}

MODE="ui"
case "${1:-}" in
  mcp) MODE="mcp"; shift ;;
  ui)  MODE="ui";  shift ;;
esac

# A bind-mounted host directory keeps its host owner, so one not owned by UID
# 1000 makes every save fail. Warn and keep going: investigations still run, and
# the mount can be fixed without a rebuild.
if [ -d /app/investigations ] && [ ! -w /app/investigations ]; then
  echo "WARNING: /app/investigations is not writable by UID $(id -u), so saved investigations will fail. Mount a named volume instead (-v robin-investigations:/app/investigations), or give the host folder to UID 1000 (sudo chown -R 1000:1000 <folder>). See \"Saved investigations fail with permission denied on Linux\" in TROUBLESHOOTING.md." >&2
fi

if [ "$MODE" = "mcp" ]; then
  # Tor is not awaited here: an MCP host expects an `initialize` reply within
  # seconds, and Tor takes ten to sixty to bootstrap. Until Tor has
  # bootstrapped, the Tor-dependent tools report `tor_bootstrapping`.
  echo "Starting Tor in the background..." >&2
  tor_with_log >&2 &

  # Warm the model list without blocking the handshake. It is never fatal: the
  # bundled models.json seed covers an offline host.
  (
    python3 -c "import model_registry; model_registry.refresh(verbose=True)" >&2 2>&2 ||
      echo "Model refresh skipped; using bundled model list." >&2
  ) &

  echo "Starting Robin MCP server (stdout is the JSON-RPC transport)..." >&2
  exec python3 -m mcp_server "$@"
fi

echo "Starting Tor..."
tor_with_log &

echo "Waiting for Tor to be ready (127.0.0.1:9050)..."

timeout 60 bash -c '
until python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect((\"127.0.0.1\", 9050)); s.close()" 2>/dev/null; do
  echo "Waiting for Tor socket..."
  sleep 2
done
'

if [ $? -ne 0 ]; then
  echo "ERROR: Tor failed to start or is not listening on port 9050."
  exit 1
fi

echo "Waiting for Tor to finish bootstrapping..."
wait_for_bootstrap 120 || echo "WARNING: Tor has not reported \"Bootstrapped 100%\" yet. Starting anyway; the first search may reach fewer engines."
echo "Tor is ready."
# Warm the model registry so the first page load already has a fresh list. It
# is never fatal: the bundled models.json seed covers an offline or Tor-only host.
echo "Refreshing model list from providers..."
python3 -c "import model_registry; model_registry.refresh(verbose=True)" || \
  echo "Model refresh skipped; using bundled model list."

echo "Starting Robin: AI-Powered Dark Web OSINT Tool..."
exec streamlit run ui.py --server.port=8501 --server.address=0.0.0.0
