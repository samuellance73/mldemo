#!/bin/bash
set -e

# Start Tailscale in userspace networking mode
tailscaled --tun=userspace-networking --state=/var/lib/tailscale/tailscaled.state --socket=/var/run/tailscale/tailscaled.sock &
TAILSCALE_PID=$!

# Wait for Tailscale socket to be ready
sleep 2

# Authenticate with Tailscale if auth key is provided
if [ -n "$TS_AUTHKEY" ]; then
    tailscale up --authkey="$TS_AUTHKEY" --hostname=openwebui --accept-routes=true || true
fi

# Start Open WebUI using the default entrypoint from the base image
exec python -c "from open_webui import main; main()"
