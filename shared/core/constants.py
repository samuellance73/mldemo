import os
from pathlib import Path

# Base paths
USER_HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAIN_ROOT = REPO_ROOT / "main"

# Directory paths
STATIC_DIR = USER_HOME / "static"
CONFIG_DIR = USER_HOME / "config"
METRICS_DIR = USER_HOME / ".torch_metrics"

# Service paths
PLAYIT_SOCKET_PATH = Path("/tmp/playit.sock")

# Network configuration
LOCALHOST = "127.0.0.1"

# Port configuration
PORTS = {
    "caddy": 7860,
    "gradio": 7861,
    "ssh": 2222,
    "chisel": 6789,
    "llm_proxy": 8080,
    "socks_proxy": 1080,
    "playit_xor_bridge": 25565,
    "minecraft": 25566,
    "open_webui": 3000,
}

# Path aliases for backward compatibility
CADDYFILE_PATH = USER_HOME / "Caddyfile"
CADDYFILE_TEMPLATE_PATH = CONFIG_DIR / "Caddyfile.template"
LOADING_HTML_PATH = CONFIG_DIR / "loading.html"
