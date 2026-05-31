import os
import subprocess
from pathlib import Path

from core.constants import CODE_SERVER_DATA_DIR, LOCALHOST
from loguru import logger

PORT = 8888
PREFIX = "[code-server]"
_DATA_DIR = CODE_SERVER_DATA_DIR


def start(log):
    """Launch code-server bound exclusively to {LOCALHOST}:{PORT}.

    ``log`` is the TeeLogger (or plain file) handle provided by setup_service_logs();
    subprocess stdout/stderr are piped through it so code-server output appears in
    the main container log stream as well as code_server.log on disk.

    Binding to localhost means the process is completely invisible on the
    public internet.  Access is routed exclusively through the Tailscale
    secure tunnel overlay or other private network paths.
    """
    Path(_DATA_DIR).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # Disable the built-in password/auth — access is controlled by Tailscale
    # network isolation.  Set to "password" and provide PASSWORD= if you need auth.
    env["DISABLE_TELEMETRY"] = "true"
    env["DISABLE_UPDATE_CHECK"] = "true"

    # Resolve binary — prefer a venv-installed copy, fall back to PATH.

    candidates = [
        "/usr/bin/code-server",
        "/usr/local/bin/code-server",
        str(Path.home() / ".local" / "bin" / "code-server"),
    ]
    binary = next((c for c in candidates if Path(c).exists()), "code-server")

    cmd = [
        binary,
        "--bind-addr",
        f"{LOCALHOST}:{PORT}",
        "--auth",
        "none",
        "--user-data-dir",
        _DATA_DIR,
        "--disable-telemetry",
    ]

    logger.info(f"{PREFIX} Starting code-server on {LOCALHOST}:{PORT}...")
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=log,
        env=env,
    )

    logger.success(
        f"{PREFIX} code-server started (pid {proc.pid}). "
        f"Reachable at http://{LOCALHOST}:{PORT} "
        f"exclusively over Tailscale / private overlay networks."
    )
