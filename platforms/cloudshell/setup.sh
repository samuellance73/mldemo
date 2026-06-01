#!/bin/bash
# platforms/cloudshell/setup.sh — Google Cloud Shell adapter
set -e

REPO_URL="${SANCTUARY_REPO:-https://github.com/your-username/sanctuary.git}"
REPO_DIR="$HOME/sanctuary"

if [ ! -d "$REPO_DIR/.git" ]; then
    git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
pip install -q uv
uv sync

# Build obfuscated dist/
uv run python main/scripts/build.py

# Launch in a persistent tmux session
tmux kill-session -t sanctuary 2>/dev/null || true
tmux new-session -d -s sanctuary "cd dist && uv run python core/orchestrator.py"
echo "[+] Sanctuary running in tmux session 'sanctuary'. Attach with: tmux attach -t sanctuary"
