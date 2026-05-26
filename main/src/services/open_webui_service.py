import os
import subprocess

from loguru import logger

METRICS_DIR = "/home/user/.torch_metrics"
LOG_PATH = os.path.join(METRICS_DIR, "open_webui.log")
PORT = 3000
PREFIX = "[open-webui]"


def start():
    """Launch Open WebUI bound exclusively to 127.0.0.1:3000.

    Binding to localhost means the process is completely invisible on the
    public internet. Nginx proxies /open-webui → 127.0.0.1:3000 so the UI
    is reachable via the HF Space URL path or directly over Tailscale.
    """
    os.makedirs(METRICS_DIR, exist_ok=True)

    env = os.environ.copy()
    # Point Open WebUI at the local LiteLLM proxy (same node).
    env["OPENAI_API_BASE_URL"] = "http://127.0.0.1:8080/v1"
    env["OPENAI_API_KEY"] = env.get("LITELLM_MASTER_KEY", "none") or "none"
    # Disable the default login wall — access is controlled by nginx path routing
    # and/or Tailscale network isolation. Enable if you want a login screen.
    env["WEBUI_AUTH"] = "False"
    # Stable secret keys so the container never regenerates them on restart.
    env.setdefault("WEBUI_SECRET_KEY", "sanctuary_owui_secret_key_server01")
    env.setdefault(
        "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY",
        "sanctuary_owui_oauth_token_key_server01_32bytes",
    )
    # Data directory inside the metrics/state folder so it survives redeploys.
    env["DATA_DIR"] = os.path.join(METRICS_DIR, "open_webui_data")
    os.makedirs(env["DATA_DIR"], exist_ok=True)

    from pathlib import Path
    open_webui_bin = "/opt/venv-openwebui/bin/open-webui" if Path("/opt/venv-openwebui/bin/open-webui").exists() else "open-webui"
    cmd = [
        open_webui_bin,
        "serve",
        "--host", "127.0.0.1",
        "--port", str(PORT),
    ]

    logger.info(f"{PREFIX} Starting Open WebUI on 127.0.0.1:{PORT}...")
    with open(LOG_PATH, "a") as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            env=env,
        )

    logger.success(f"{PREFIX} Open WebUI started (pid {proc.pid}). "
                   f"Reachable at http://127.0.0.1:{PORT} "
                   f"or via nginx at /open-webui")
