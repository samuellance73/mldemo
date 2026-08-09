from pathlib import Path

# Base paths
USER_HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAIN_ROOT = REPO_ROOT / "main"

# Directory paths
STATIC_DIR = USER_HOME / "static"

# Find config directory dynamically across all environments (Docker, VM dist, or uncompiled dev)
CURRENT_FILE = Path(__file__).resolve()
CONFIG_CANDIDATES = [
    USER_HOME / "config",                                  # Container runtime (~/config)
    CURRENT_FILE.parent.parent.parent / "config",          # VM dist runtime (main/dist/config)
    CURRENT_FILE.parent.parent.parent.parent / "config",   # Uncompiled source dev runtime (Sanctuary/config)
]

CONFIG_DIR = USER_HOME / "config"  # Fallback default

# 1. First pass: look for a directory that actually contains enabled_services.json
for path in CONFIG_CANDIDATES:
    if (path / "enabled_services.json").is_file():
        CONFIG_DIR = path
        break
else:
    # 2. Second pass: fallback to the first candidate that is a directory
    for path in CONFIG_CANDIDATES:
        if path.is_dir():
            CONFIG_DIR = path
            break

ENABLED_SERVICES_PATH = CONFIG_DIR / "enabled_services.json"




METRICS_DIR = USER_HOME / ".torch_metrics"
VENV_OPENWEBUI_DIR = USER_HOME / ".venv-openwebui"
FILEBROWSER_DB_PATH = USER_HOME / "filebrowser.db"
LITELLM_CONFIG_PATH = USER_HOME / "litellm.yaml"
LITELLM_KEYS_PATH = USER_HOME / "llm_keys.yaml"
LITELLM_BASE_CONFIG_PATH = CONFIG_DIR / "litellm_base.yaml"
CODE_SERVER_DATA_DIR = METRICS_DIR / "code_server_data"
TAILSCALE_STATE_DIR = METRICS_DIR
TAILSCALE_SOCKET_PATH = METRICS_DIR / "tailscaled.sock"
SLIVER_HOME = METRICS_DIR / "sliver"

# Service paths
PLAYIT_SOCKET_PATH = Path("/tmp/playit.sock")

# Network configuration
LOCALHOST = "127.0.0.1"

# Port configuration
PORTS = {
    "caddy": 7860,
    "caddy_secondary": 7890,
    "portal": 7861,
    "ssh": 2222,
    "chisel": 6789,
    "gost": 6790,
    "model_sync": 6795,
    "sliver": 11601,
    "llm_proxy": 8080,
    "filebrowser": 9000,
    "socks_proxy": 1080,
    "playit_xor_bridge": 25565,
    "minecraft": 25566,
    "open_webui": 3000,
    "visual_debugger": 8501,
    "tmate": 2200,
    "scramjet": 8085,
}

# Path aliases for backward compatibility
CADDYFILE_PATH = USER_HOME / "Caddyfile"
CADDYFILE_TEMPLATE_PATH = CONFIG_DIR / "Caddyfile.template"
LOADING_HTML_PATH = CONFIG_DIR / "loading.html"
