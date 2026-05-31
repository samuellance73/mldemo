import sys
import threading
import time

from core.constants import METRICS_DIR, STATIC_DIR, USER_HOME
from loguru import logger

LOG_PATH = METRICS_DIR / "test.log"
STARTUP_LOG = METRICS_DIR / "startup.log"
MARKER_PATH = USER_HOME / "TEST_SERVICE_IS_ACTIVE"
STATIC_BANNER = STATIC_DIR / "TEST_SERVICE_ENABLED.txt"
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
        with LOG_PATH.open("a") as f:
            f.write(line)
    except OSError:
        pass
    try:
        with STARTUP_LOG.open("a") as f:
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
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    started = "Started at " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    with LOG_PATH.open("a") as f:
        f.write(BANNER)
        f.write(started + "\n")

    MARKER_PATH.write_text("TEST SERVICE IS ACTIVE\nSee also: " + str(LOG_PATH) + "\n")
    STATIC_BANNER.write_text(BANNER.strip() + "\n")

    for line in BANNER.strip().split("\n"):
        _emit(line.strip())
    _emit(started)
    _emit("marker file: " + str(MARKER_PATH))
    _emit("full log: " + str(LOG_PATH) + " (also Gradio command SHOW_LOGS_TEST)")

    logger.success(BANNER.strip())
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
