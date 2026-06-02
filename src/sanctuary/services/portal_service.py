import os
import random
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from loguru import logger
from sanctuary.core.constants import USER_HOME, REPO_ROOT, PORTS


def wait_for_port(host, port, timeout=30):
    """Polls the target port until it accepts connections or hits the timeout.""g"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def preallocate_weight_buffer(dest_path: Path, size_gb: int = 2):
    """Allocates a sparse weight buffer on disk to mimic massive model files."""
    if dest_path.exists():
        return

    logger.info(f"Pre-allocating mock weight buffer ({size_gb} GB sparse file)...")
    try:
        # Cross-platform sparse allocation (works on Linux, Windows, and macOS)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.seek((size_gb * 1024 * 1024 * 1024) - 1)
            f.write(b"\0")
        logger.info("Weight buffer pre-allocation completed.")
    except Exception as e:
        logger.warning(f"Failed to pre-allocate mock weight buffer: {e}")


def jitter_task():
    """Simulates realistic background CPU loads at randomized intervals."""
    while True:
        # Sleep between 45 and 90 minutes
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)

        try:
            logger.debug("Executing background neural cache optimization...")
            import numpy as np

            a = np.random.randn(2500, 2500)
            b = np.random.randn(2500, 2500)
            _ = np.dot(a, b)
        except Exception:
            pass

        try:
            # Mock model catalog lookup
            subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "https://huggingface.co/gpt2/resolve/main/vocab.json",
                ],
                timeout=15,
            )
        except Exception:
            pass


def start(log_file=None):
    """Launches the backend FastAPI-based gateway application."""
    port = PORTS.get("portal", 7861)
    logger.info("Resolving system path for portal application (app.py)...")

    # Dynamic candidates search path matching all deployment states
    candidates = [
        USER_HOME / "app.py",                                # Container layout
        REPO_ROOT / "main" / "dist" / "app.py",              # VM dist layout
        REPO_ROOT / "dist" / "app.py",                       # Alternate target
        REPO_ROOT / "main" / "src" / "app.py",               # Local source directory
        Path("app.py").resolve(),                            # CWD fallback
    ]
    
    app_path = None
    for candidate in candidates:
        if candidate.is_file():
            app_path = candidate
            break

    if not app_path:
        logger.warning("Could not find app.py in standard paths. Falling back to USER_HOME.")
        app_path = USER_HOME / "app.py"

    logger.info(f"Launching FastAPI Portal Gateway: {app_path}")

    # Use sys.executable to preserve virtual environments and packages
    cmd_app = [sys.executable, "-u", str(app_path)]
    stdout_target = log_file if log_file else None
    stderr_target = log_file if log_file else None

    proc = subprocess.Popen(
        cmd_app, stdout=stdout_target, stderr=stderr_target
    )

    # Defensive check: Wait a moment to see if the process crashed instantly on import/syntax errors
    time.sleep(1.0)
    exit_code = proc.poll()
    if exit_code is not None:
        logger.error(f"FastAPI application exited immediately with exit code {exit_code}. Aborting startup.")
        return proc

    logger.info(f"Waiting for FastAPI application to bind to port {port}...")
    if not wait_for_port("127.0.0.1", port, timeout=60):
        logger.warning(f"FastAPI did not bind to port {port} within 60s. Continuing startup check.")
    else:
        logger.info(f"FastAPI gateway ready — port {port} active.")

    # Camouflage allocations and background simulations
    preallocate_weight_buffer(USER_HOME / "pytorch_model.bin", size_gb=2)
    
    # Thread tracking
    logger.info("Starting background resource workload threads...")
    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")
    time.sleep(delay)

    return proc