import os
import sys
import threading
from pathlib import Path
from typing import Dict

from loguru import logger
from sanctuary.core.constants import METRICS_DIR

COVERT_LOGGING_MODE = 2
METRICS_DIR_PATH = Path(METRICS_DIR)


class ServiceLogPipe:
    """
    RAII Pattern: A self-cleaning OS pipe that reads from a subprocess 
    and forwards the data to Loguru, closing safely when destroyed.
    """
    def __init__(self, prefix: str):
        self.prefix = prefix
        self._closed = False
        
        # Create the OS-level memory tunnel
        self._r, self._w = os.pipe()
        
        # Spawn the background worker specifically for this pipe
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"LogReader-{prefix}",
            daemon=True
        )
        self._thread.start()

    def fileno(self) -> int:
        """Duck-typing: Allows subprocess.Popen to treat this object as a file."""
        return self._w

    def write(self, s: str):
        """Allows manual string writes from Python service scripts (e.g., service.write())."""
        logger.bind(prefix=self.prefix).info(s.rstrip("\r\n"))

    def flush(self):
        """Mock flush method to satisfy standard file-like interfaces."""
        pass

    def _read_loop(self):
        """The background loop that consumes the pipe."""
        try:
            with os.fdopen(self._r, "r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    logger.bind(prefix=self.prefix).info(line.rstrip("\r\n"))
        except Exception as e:
            logger.error(f"Pipe reader for {self.prefix} failed: {e}")
        finally:
            self.close()

    def close(self):
        """Safely shuts down the write end of the pipe, preventing OS resource leaks."""
        if not self._closed:
            self._closed = True
            try:
                os.close(self._w)
            except OSError:
                pass 

    def __del__(self):
        self.close()


class LogRegistry:
    """
    Open/Closed Principle & Lazy Evaluation:
    Dynamically generates log files and pipes ONLY when they are requested.
    """
    def __init__(self, output_dir: Path, covert_mode: int):
        self.output_dir = output_dir
        self.covert_mode = covert_mode
        self._pipes: Dict[str, ServiceLogPipe] = {}
        
        # Reset Loguru
        logger.remove()
        
        if self.covert_mode in (1, 2):
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
        if self.covert_mode == 2:
            # Fix 1: Use a dynamic formatter function to prevent KeyError on empty extra dicts
            def console_formatter(record):
                if "prefix" in record["extra"]:
                    return "<cyan>[{extra[prefix]}]</cyan> <level>{message}</level>\n"
                # Fallback format for global system logs (which have no prefix)
                return "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>\n"

            logger.add(
                sys.stdout,
                format=console_formatter,
                level="INFO",
                enqueue=True
            )

    def __getattr__(self, service_name: str) -> ServiceLogPipe:
        """Dynamic attribute lookup."""
        if service_name in self._pipes:
            return self._pipes[service_name]

        prefix = service_name.upper()

        if self.covert_mode in (1, 2):
            filepath = self.output_dir / f"{service_name}.log"
            
            logger.add(
                str(filepath),
                filter=lambda record, p=prefix: record["extra"].get("prefix") == p,
                format="{message}",
                level="INFO",
                enqueue=True
            )

        new_pipe = ServiceLogPipe(prefix)
        self._pipes[service_name] = new_pipe
        
        return new_pipe


def setup_service_logs() -> LogRegistry:
    """Returns the dynamic registry."""
    return LogRegistry(METRICS_DIR_PATH, COVERT_LOGGING_MODE)