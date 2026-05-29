#!/bin/bash
# Start socat in the background to forward port 7860 (Hugging Face Space entry point) to 6901 (KasmVNC internal)
echo "Starting socat port forwarder (7860 -> 6901)..."
socat TCP-LISTEN:7860,fork,reuseaddr TCP:127.0.0.1:6901 &
echo "socat started in background."
