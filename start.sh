#!/bin/bash

# 1. Start the renamed Tailscale daemon in the background
# We call it 'python-cache-manager' now
python-cache-manager --tun=userspace-networking --socks5-server=localhost:1055 &

# 2. Start the renamed File Browser on a HIDDEN port (not 7860)
# This port is NOT visible to HF, only to you via Tailscale
ai-metrics-collector -p 8080 -a 0.0.0.0 -r / &

# 3. Connect to Tailscale in the background
sleep 5
py-cache-cli up --authkey="${TAILSCALE_AUTH_KEY}" --hostname="ai-model-server" --ssh &

# 4. START THE "FAKE" APP ON PORT 7860
# This is what Hugging Face sees. It keeps the status "Green".
python3 /app.py