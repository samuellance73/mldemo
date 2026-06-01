#!/bin/bash
set -e

# Only start Tailscale when an auth key is supplied; otherwise skip entirely
# to avoid crash-loop noise in environments without a key configured.
if [ -n "$TS_AUTHKEY" ]; then
    mkdir -p /var/lib/tailscale /var/run/tailscale
    tailscaled \
        --tun=userspace-networking \
        --state=/var/lib/tailscale/tailscaled.state \
        --socket=/var/run/tailscale/tailscaled.sock &
    # Wait for socket to become ready
    for i in $(seq 1 10); do
        [ -S /var/run/tailscale/tailscaled.sock ] && break
        sleep 1
    done
    tailscale up --authkey="$TS_AUTHKEY" --hostname=openwebui --accept-routes=true || true
fi

# Launch Open WebUI via its installed CLI (correct entrypoint for the base image)
exec open-webui serve --host "${HOST:-0.0.0.0}" --port "${PORT:-7860}"
