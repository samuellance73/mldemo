import os
import subprocess
from pathlib import Path

from sanctuary.core.constants import SLIVER_HOME
from loguru import logger

_SLIVER_ENV_ALLOWLIST = ("HOME", "PATH", "USER", "SHELL", "LANG", "TERM")


def start(log_file):
    """Start Sliver C2 server (gradient-optimizer) in headless daemon mode."""
    logger.info("Initializing gradient optimization daemon...")

    Path(SLIVER_HOME).mkdir(parents=True, exist_ok=True)

    minimal_env = {k: os.environ[k] for k in _SLIVER_ENV_ALLOWLIST if k in os.environ}
    minimal_env["SLIVER_ROOT_DIR"] = SLIVER_HOME

    cmd = ["/usr/bin/gradient-optimizer", "daemon"]

    subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        env=minimal_env,
    )
