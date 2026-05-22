import os
import sys
import threading
import time

from loguru import logger

METRICS_DIR = "/home/user/.torch_metrics"
LOG_PATH = os.path.join(METRICS_DIR, "test.log")
STARTUP_LOG = os.path.join(METRICS_DIR, "startup.log")
MARKER_PATH = "/home/user/TEST_SERVICE_IS_ACTIVE"
STATIC_BANNER = "/home/user/static/TEST_SERVICE_ENABLED.txt"
PREFIX = "[TEST SERVICE]"

BANNER = """
================================================================================
  TEST SERVICE IS RUNNING — per-node services selection is working.
================================================================================
"""


def _emit(msg):
    """Write to container stdout (visible via cc.py --logs) and test.log."""
    line = PREFIX + " " + msg.rstrip() + "\n"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.write(line)
            stream.flush()
        except OSError:
            pass
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass
    try:
        with open(STARTUP_LOG, "a") as f:
            f.write(line)
    except OSError:
        pass


def _heartbeat_loop():
    while True:
        time.sleep(15)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        _emit("HEARTBEAT at " + ts + " — still alive")


def start():
    """Obvious smoke-test service: marker files, banner log, periodic heartbeats."""
    os.makedirs(METRICS_DIR, exist_ok=True)
    os.makedirs("/home/user/static", exist_ok=True)

    started = "Started at " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    with open(LOG_PATH, "a") as f:
        f.write(BANNER)
        f.write(started + "\n")

    with open(MARKER_PATH, "w") as f:
        f.write("TEST SERVICE IS ACTIVE\n")
        f.write("See also: " + LOG_PATH + "\n")

    with open(STATIC_BANNER, "w") as f:
        f.write(BANNER.strip() + "\n")

    for line in BANNER.strip().split("\n"):
        _emit(line.strip())
    _emit(started)
    _emit("marker file: " + MARKER_PATH)
    _emit("full log: " + LOG_PATH + " (also Gradio command SHOW_LOGS_TEST)")

    logger.success(BANNER.strip())
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
