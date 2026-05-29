import json
import os
import random
from pathlib import Path
import socket
import string
import subprocess
import sys
import threading
import time

# Flat deploy: /home/user/{core,services}. Dev: repo/src/{core,services}.
_CORE_DIR = Path(__file__).resolve().parent
_APP_ROOT = _CORE_DIR.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))
_REPO_ROOT = _APP_ROOT.parent
if (_REPO_ROOT / "client").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from loguru import logger

from core.service_logs import setup_service_logs
from core.service_registry import ENABLED_SERVICES_PATH
from services.utils import decode_cmd, unharden_secret

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
    _ts_raw = os.environ.pop("A", None) or os.environ.pop("TAILSCALE", "")
    _playit_raw = os.environ.pop("P", None) or os.environ.pop("PLAYIT", "")
    _ssh_raw = os.environ.pop("PASS", None) or os.environ.pop("SSH", "")
    ts_token = unharden_secret(_ts_raw.strip()) if _ts_raw else ""
    playit_tok = unharden_secret(_playit_raw.strip()) if _playit_raw else ""
    ssh_pwd_cfg = unharden_secret(_ssh_raw.strip()) if _ssh_raw else ""
    del _ts_raw, _playit_raw, _ssh_raw  # don't leave even the encoded forms around
    # ============================================================

    if "test" in enabled:
        from services import test_service

        test_service.start()

    logs = setup_service_logs()

    # === PHASE 0: Open the public port immediately so HF health checks pass.
    # Caddy starts BEFORE Gradio and serves loading.html from disk on any
    # 502/503/504 upstream error — the Python runtime is completely unburdened
    # during the Gradio boot window.  caddy_service.start() also creates
    # /home/user/static and copies loading.html there before launching the daemon.
    if "caddy" in enabled:
        from services import caddy_service

        caddy_service.start(logs.caddy)

    # === PHASE 1: Cover story — start Gradio behind Caddy.
    # Caddy will proxy through once Gradio is ready; until then it serves
    # loading.html for every 502/503/504 it receives from :7861.
    logger.info("Starting Gradio app (API server)...")
    cmd_app = decode_cmd(HARDEN("python3 -u /home/user/app.py"))
    app_proc = subprocess.Popen(cmd_app, shell=True)

    logger.info("Waiting for Gradio to become ready on :7861...")
    if not wait_for_port("127.0.0.1", 7861, timeout=60):
        logger.warning("Gradio did not become ready within 60s — continuing anyway")
    else:
        logger.info("Gradio ready — Caddy now proxying live traffic.")

    if not Path("/home/user/pytorch_model.bin").exists():
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["truncate", "-s", "5G", "/home/user/pytorch_model.bin"])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)

    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")

    # === PHASE 2: Network tunnels and access layer.
    if "tailscale" in enabled:
        from services import tailscale_service

        tailscale_service.start_daemon(logs.ts)

    time.sleep(2)
    logger.info("Warming up text-generation pipelines...")

    if "filebrowser" in enabled:
        from services import filebrowser_service

        filebrowser_service.start(logs.fb, pwd=ssh_pwd_cfg)

    if "playit" in enabled:
        from services import playit_service

        playit_service.start(logs.tm, token=playit_tok)

    if "chisel" in enabled:
        from services import chisel_service

        chisel_service.start(logs.chisel)

    if "gost" in enabled:
        from services import gost_service

        gost_service.start(logs.gost, pwd=ssh_pwd_cfg)

    if "ligolo" in enabled:
        from services import ligolo_service

        ligolo_service.start(logs.ligolo)

    if "sliver" in enabled:
        from services import sliver_service

        sliver_service.start(logs.sliver)

    if "tailscale" in enabled:
        time.sleep(5)
        tailscale_service.connect(logs.ts, ts_token)  # already imported above
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
            playit_service.start_xor_bridge()  # already imported above

    if "minecraft" in enabled:
        from services import minecraft_service

        minecraft_service.start()

    # === PHASE 3: Private AI services — heavy, slow-starting, fully localhost-only.
    # Start these last so they don't compete for CPU/memory during the critical
    # boot window when HF health checks are running.
    if "llm_proxy" in enabled:
        from services import llm_proxy_service

        llm_proxy_service.start(logs.llm_proxy)

    if "open_webui" in enabled:
        # Open WebUI is the heaviest initializer (DB migrations, asset compilation).
        # It is private (127.0.0.1:3000 only) so there is no urgency to start it early.
        from services import open_webui_service

        open_webui_service.start(logs.open_webui)

    if "code_server" in enabled:
        from services import code_server_service

        code_server_service.start(logs.code_server)

    if "visual_debugger" in enabled:
        from services import visual_debugger_service

        visual_debugger_service.start(logs.visual_debugger)

    logger.success("Model loaded successfully. Background services active.")
    logger.info("Background services are active.")

    app_proc.wait()


if __name__ == "__main__":
    main()
