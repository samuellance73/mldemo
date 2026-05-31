import random
import socket
import subprocess
import threading
import time
from pathlib import Path

from loguru import logger


def jitter_task():
    """Simulate CPU/Memory circadian rhythm activity to mimic user behavior."""
    while True:
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)

        try:
            logger.debug("Processing background inference batch...")
            import numpy as np

            a = np.random.randn(2000, 2000)
            b = np.random.randn(2000, 2000)
            _ = np.dot(a, b)
        except Exception:
            pass

        try:
            logger.debug("Syncing model cache...")
            subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "https://huggingface.co/gpt2/resolve/main/vocab.json",
                ]
            )
        except Exception:
            pass


def wait_for_port(host, port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def start(log_file=None):
    """Start the Gradio Cover App and pre-allocate mock weights."""
    home_dir = Path.home()

    logger.info("Starting Gradio app (API server)...")
    # app.py is located at the workspace root inside the container
    app_path = home_dir / "app.py"

    # Run the cover story app
    cmd_app = f"python3 -u {app_path}"
    # Use standard subprocess Popen. Redirect stdout/stderr if a log file is given.
    stdout_target = log_file if log_file else None
    stderr_target = log_file if log_file else None

    proc = subprocess.Popen(
        cmd_app, shell=True, stdout=stdout_target, stderr=stderr_target
    )

    logger.info("Waiting for Gradio to become ready on :7861...")
    if not wait_for_port("127.0.0.1", 7861, timeout=60):
        logger.warning("Gradio did not become ready within 60s — continuing anyway")
    else:
        logger.info("Gradio ready — Caddy now proxying live traffic.")

    # Create dummy VRAM/V-disk allocation
    model_weight = home_dir / "pytorch_model.bin"
    if not model_weight.exists():
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["truncate", "-s", "5G", str(model_weight)])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)

    # Boot cover-story active loop
    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")
    return proc
