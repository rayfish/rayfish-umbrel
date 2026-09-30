#!/bin/sh
# Entrypoint for the rayfish Umbrel app: GUI, GUI proxy, and daemon in one
# container. The daemon runs as PID 1 so its exit restarts the container.
set -eu

GUI_PORT="${GUI_PORT:-8481}"
PROXY_PORT="${PROXY_PORT:-8480}"
GUI_LOG=/tmp/gui.log

# First boot only: default the mesh hostname to "umbrel" so networks are
# joined as umbrel (reachable at umbrel.<network>.ray). ray otherwise falls
# back to a random generated name. Never touches an existing settings.toml.
if [ ! -f /etc/rayfish/settings.toml ]; then
    mkdir -p /etc/rayfish
    printf 'default_hostname = "umbrel"\n' > /etc/rayfish/settings.toml
    chmod 600 /etc/rayfish/settings.toml
fi
mkdir -p /etc/rayfish/downloads

# ray gui binds 127.0.0.1 and mints a random token, printed in its startup
# URL. Start it, scrape the token, and hand it to the proxy that exposes the
# GUI on the LAN (Umbrel links straight to http://<device>:8480).
rm -f "$GUI_LOG"
ray gui --port "$GUI_PORT" --no-open >"$GUI_LOG" 2>&1 &

token=""
tries=0
while [ "$tries" -lt 100 ]; do
    token="$(sed -n 's/.*token=\([0-9a-f]\{32\}\).*/\1/p' "$GUI_LOG" | head -n 1)"
    [ -n "$token" ] && break
    tries=$((tries + 1))
    sleep 0.2
done
if [ -z "$token" ]; then
    echo "rayfish-start: ray gui did not report a token; output was:" >&2
    cat "$GUI_LOG" >&2 || true
    exit 1
fi

GUI_TOKEN="$token" GUI_UPSTREAM_PORT="$GUI_PORT" LISTEN_PORT="$PROXY_PORT" \
    python3 /usr/local/lib/rayfish/gui-proxy.py &

exec ray daemon
