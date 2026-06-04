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
        
        # 1. Create the OS-level memory tunnel
        self._r, self._w = os.pipe()
        
        # 2. Spawn the background worker specifically for this pipe
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"LogReader-{prefix}",
            daemon=True
        )
        self._thread.start()

    def fileno(self) -> int:
        """Duck-typing: Allows subprocess.Popen to treat this object as a file."""
        return self._w

    def _read_loop(self):
        """The background loop that consumes the pipe."""
        try:
            # Context manager ensures the read end is closed when the loop ends
            with os.fdopen(self._r, "r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    # Bind the prefix to the log and strip carriage returns
                    logger.bind(prefix=self.prefix).info(line.rstrip("\r\n"))
        except Exception as e:
            logger.error(f"Pipe reader for {self.prefix} failed: {e}")
        finally:
            # RAII: Guarantee cleanup even if the loop crashes
            self.close()

    def close(self):
        """Safely shuts down the write end of the pipe, preventing OS resource leaks."""
        if not self._closed:
            self._closed = True
            try:
                os.close(self._w)
            except OSError:
                pass # Already closed by the OS

    def __del__(self):
        """Fallback: If Python garbage collects this object, close the pipe."""
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
        
        # Reset Loguru and configure the master console output
        logger.remove()
        
        if self.covert_mode in (1, 2):
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
        if self.covert_mode == 2:
            logger.add(
                sys.stdout,
                format="<cyan>[{extra[prefix]}]</cyan> <level>{message}</level>",
                level="INFO",
                enqueue=True
            )

    def __getattr__(self, service_name: str) -> ServiceLogPipe:
        """
        PYTHONIC MAGIC: This intercepts requests for attributes that don't exist.
        If orchestrator.py calls `logs.chisel`, this method catches "chisel",
        builds the pipe, configures the file, and returns it dynamically.
        """
        # If we have already built this pipe, return it instantly
        if service_name in self._pipes:
            return self._pipes[service_name]

        # 1. Normalize the name (e.g., "chisel" -> "CHISEL")
        prefix = service_name.upper()

        # 2. Lazy Evaluation: Only create the file on disk if requested
        if self.covert_mode in (1, 2):
            filepath = self.output_dir / f"{service_name}.log"
            
            logger.add(
                str(filepath),
                filter=lambda record, p=prefix: record["extra"].get("prefix") == p,
                format="{message}",
                level="INFO",
                enqueue=True
            )

        # 3. Create the pipe, store it in the dictionary, and return it
        new_pipe = ServiceLogPipe(prefix)
        self._pipes[service_name] = new_pipe
        
        return new_pipe


def setup_service_logs() -> LogRegistry:
    """Returns the dynamic registry. Replaces the old namedtuple."""
    return LogRegistry(METRICS_DIR_PATH, COVERT_LOGGING_MODE)