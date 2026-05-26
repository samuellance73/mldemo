import os
import sys
import threading
from collections import namedtuple

COVERT_LOGGING_MODE = 1

METRICS_DIR = "/home/user/.torch_metrics"

ServiceLogs = namedtuple(
    "ServiceLogs",
    ["ts", "fb", "tm", "chisel", "gost", "ligolo", "sliver", "caddy"],
)


class TeeLogger:
    def __init__(self, filepath, prefix):
        self.file = open(filepath, "a")
        self.prefix = prefix
        r, w = os.pipe()
        self.r = r
        self.w = w
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        rf = os.fdopen(self.r, "r", errors="replace")
        try:
            for line in rf:
                self.file.write(line)
                self.file.flush()
                sys.stdout.write(f"[{self.prefix}] {line}")
                sys.stdout.flush()
        except Exception:
            pass

    def fileno(self):
        return self.w

    def write(self, s):
        self.file.write(s)
        self.file.flush()
        sys.stdout.write(
            f"[{self.prefix}] {s}\n" if not s.endswith("\n") else f"[{self.prefix}] {s}"
        )
        sys.stdout.flush()

    def flush(self):
        self.file.flush()
        sys.stdout.flush()


def _open_log_files():
    return (
        open(f"{METRICS_DIR}/ts_daemon.log", "a"),
        open(f"{METRICS_DIR}/fb.log", "a"),
        open(f"{METRICS_DIR}/tm_daemon.log", "a"),
        open(f"{METRICS_DIR}/chisel.log", "a"),
        open(f"{METRICS_DIR}/gost.log", "a"),
        open(f"{METRICS_DIR}/ligolo.log", "a"),
        open(f"{METRICS_DIR}/sliver.log", "a"),
        open(f"{METRICS_DIR}/caddy.log", "a"),
    )


def _tee_loggers():
    return (
        TeeLogger(f"{METRICS_DIR}/ts_daemon.log", "TS"),
        TeeLogger(f"{METRICS_DIR}/fb.log", "FB"),
        TeeLogger(f"{METRICS_DIR}/tm_daemon.log", "PLAYIT"),
        TeeLogger(f"{METRICS_DIR}/chisel.log", "CHISEL"),
        TeeLogger(f"{METRICS_DIR}/gost.log", "GOST"),
        TeeLogger(f"{METRICS_DIR}/ligolo.log", "LIGOLO"),
        TeeLogger(f"{METRICS_DIR}/sliver.log", "SLIVER"),
        TeeLogger(f"{METRICS_DIR}/caddy.log", "CADDY"),
    )


def _devnull_logs():
    devnull = open(os.devnull, "w")
    return (devnull,) * 8


def setup_service_logs():
    """Initialize per-service log sinks based on COVERT_LOGGING_MODE."""
    if COVERT_LOGGING_MODE in (1, 2):
        os.makedirs(METRICS_DIR, exist_ok=True)

    if COVERT_LOGGING_MODE == 1:
        logs = _open_log_files()
    elif COVERT_LOGGING_MODE == 2:
        logs = _tee_loggers()
    else:
        logs = _devnull_logs()

    return ServiceLogs(*logs)
