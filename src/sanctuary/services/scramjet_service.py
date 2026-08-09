"""Scramjet Service Module for Sanctuary.

Launches the official Node.js Scramjet Proxy Engine (scramjet_server.js) using the
@mercuryworkshop/scramjet WASM rewriter and @tomphttp/bare-server-node protocol.
"""

import os
import subprocess
import sys
from pathlib import Path
from loguru import logger

try:
    from sanctuary.core.constants import PORTS
    DEFAULT_PORT = PORTS.get("scramjet", 7860)
except ImportError:
    DEFAULT_PORT = 7860

PREFIX = "[SCRAMJET]"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", os.environ.get("SCRAMJET_PORT", DEFAULT_PORT)))


def start(log):
    """Launch Scramjet Proxy service bound to HOST:PORT."""
    logger.info(f"{PREFIX} Starting Scramjet Proxy server on {HOST}:{PORT}...")

    node_bin = subprocess.run(["which", "node"], capture_output=True, text=True).stdout.strip()
    scramjet_js = Path(__file__).parent / "scramjet_server.js"

    if node_bin and scramjet_js.exists():
        logger.info(f"{PREFIX} Launching Node.js Scramjet WASM engine ({scramjet_js})...")
        out_target = log if hasattr(log, "fileno") else None
        proc = subprocess.Popen(
            [node_bin, str(scramjet_js), str(PORT)],
            stdout=out_target,
            stderr=out_target,
            env=os.environ.copy()
        )
        logger.success(f"{PREFIX} Scramjet Node.js WASM daemon started (pid {proc.pid}) on port {PORT}.")
        return proc
    else:
        logger.error(f"{PREFIX} Node.js binary or scramjet_server.js not found.")
        return None


if __name__ == "__main__":
    class DummyLog:
        def write(self, msg):
            sys.stdout.write(msg)
        def flush(self):
            sys.stdout.flush()

    start(DummyLog())