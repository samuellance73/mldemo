#!/bin/bash

echo "Starting Tailscale Daemon in userspace mode..."
# We must use userspace-networking because HF doesn't allow root TUN devices
tailscaled --tun=userspace-networking --socks5-server=localhost:1055&

# Wait 3 seconds for the daemon to wake up
sleep 3

echo "Connecting to Tailnet..."
# Log in using the secret key we saved in HF Settings
tailscale up --authkey="${TAILSCALE_AUTH_KEY}" --hostname="hf-ubuntu-server"  --ssh 

echo "Starting File Browser..."
# Start File Browser on port 7860 (HF's default port)
# This keeps the Docker container alive and gives you a UI!
filebrowser -p 7860 -a 0.0.0.0 -r /