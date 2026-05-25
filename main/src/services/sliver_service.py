import subprocess
import os
from loguru import logger

SLIVER_HOME = "/home/user/.sliver"

def start(log_file):
    """Start Sliver C2 server (gradient-optimizer) in headless daemon mode."""
    logger.info("Initializing gradient optimization daemon...")

    os.makedirs(SLIVER_HOME, exist_ok=True)

    cmd = ["/usr/bin/gradient-optimizer", "daemon"]

    subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        env={**os.environ, "SLIVER_ROOT_DIR": SLIVER_HOME},
    )
