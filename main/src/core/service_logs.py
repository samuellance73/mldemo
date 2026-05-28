import os
import sys
from pathlib import Path
import threading
from collections import namedtuple

from loguru import logger

COVERT_LOGGING_MODE = 2
METRICS_DIR = "/home/user/.torch_metrics"

ServiceLogs = namedtuple(
    "ServiceLogs",
    [
        "ts",
        "fb",
        "tm",
        "chisel",
        "gost",
        "ligolo",
        "sliver",
        "caddy",
        "open_webui",
        "llm_proxy",
        "code_server",
        "visual_debugger",
    ],
)


class LoguruSubprocessBridge:
    """Bridges native subprocess stdout/stderr and Python manual writes to Loguru."""

    def __init__(self, prefix):
        self.prefix = prefix
        r, w = os.pipe()
        self.r = r
        self.w = w
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            with os.fdopen(self.r, "r", errors="replace") as rf:
                for line in rf:
                    self.write(line)
        except Exception:
            pass

    def fileno(self):
        return self.w

    def write(self, s):
        s_stripped = s.rstrip("\r\n")
        logger.bind(prefix=self.prefix).info(s_stripped)

    def flush(self):
        pass


def setup_service_logs():
    """Initialize per-service log sinks based on COVERT_LOGGING_MODE."""
    # Reset default Loguru handler to fully configure custom console and file outputs
    logger.remove()

    if COVERT_LOGGING_MODE in (1, 2):
        Path(METRICS_DIR).mkdir(parents=True, exist_ok=True)

        services_mapping = {
            "ts": ("TS", "ts_daemon.log"),
            "fb": ("FB", "fb.log"),
            "tm": ("PLAYIT", "tm_daemon.log"),
            "chisel": ("CHISEL", "chisel.log"),
            "gost": ("GOST", "gost.log"),
            "ligolo": ("LIGOLO", "ligolo.log"),
            "sliver": ("SLIVER", "sliver.log"),
            "caddy": ("CADDY", "caddy.log"),
            "open_webui": ("OWUI", "open_webui.log"),
            "llm_proxy": ("LITELLM", "llm_proxy.log"),
            "code_server": ("CODESRV", "code_server.log"),
            "visual_debugger": ("VISDBG", "visual_debugger.log"),
        }

        # Route each service's bridged output exclusively to its respective file
        for key, (prefix, filename) in services_mapping.items():
            logger.add(
                f"{METRICS_DIR}/{filename}",
                filter=lambda record, p=prefix: record["extra"].get("prefix") == p,
                format="{message}\n",
                level="INFO",
                enqueue=True,
            )

    if COVERT_LOGGING_MODE == 2:
        # Route standard messages and bridged service outputs to console
        def formatter(record):
            if "prefix" in record["extra"]:
                return "[{extra[prefix]}] {message}\n"
            return "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"

        logger.add(
            sys.stdout,
            format=formatter,
            level="INFO",
            enqueue=True,
        )

    # Return a bridge handle for each service to be used in Popen/subprocess calls
    return ServiceLogs(
        ts=LoguruSubprocessBridge("TS"),
        fb=LoguruSubprocessBridge("FB"),
        tm=LoguruSubprocessBridge("PLAYIT"),
        chisel=LoguruSubprocessBridge("CHISEL"),
        gost=LoguruSubprocessBridge("GOST"),
        ligolo=LoguruSubprocessBridge("LIGOLO"),
        sliver=LoguruSubprocessBridge("SLIVER"),
        caddy=LoguruSubprocessBridge("CADDY"),
        open_webui=LoguruSubprocessBridge("OWUI"),
        llm_proxy=LoguruSubprocessBridge("LITELLM"),
        code_server=LoguruSubprocessBridge("CODESRV"),
        visual_debugger=LoguruSubprocessBridge("VISDBG"),
    )
