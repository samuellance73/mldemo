import json
import os
import random
import socket
import string
import subprocess
import sys
import time
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parent
_APP_ROOT = _CORE_DIR.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))
_REPO_ROOT = _APP_ROOT.parent
if (_REPO_ROOT / "client").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from loguru import logger
from services.utils import unharden_secret

from core.constants import LOCALHOST, PORTS
from core.service_logs import setup_service_logs
from core.service_registry import ENABLED_SERVICES_PATH

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

    _ts_raw = os.environ.pop("A", None) or os.environ.pop("TAILSCALE", "")
    _playit_raw = os.environ.pop("P", None) or os.environ.pop("PLAYIT", "")
    _ssh_raw = os.environ.pop("PASS", None) or os.environ.pop("SSH", "")
    ts_token = unharden_secret(_ts_raw.strip()) if _ts_raw else ""
    playit_tok = unharden_secret(_playit_raw.strip()) if _playit_raw else ""
    ssh_pwd_cfg = unharden_secret(_ssh_raw.strip()) if _ssh_raw else ""
    del _ts_raw, _playit_raw, _ssh_raw

    if "test" in enabled:
        from services import test_service

        test_service.start()

    logs = setup_service_logs()

    if "caddy" in enabled:
        from services import caddy_service

        caddy_service.start(logs.caddy)

    if "gradio" in enabled:
        from services import gradio_service

        gradio_proc = gradio_service.start(logs.gradio)

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
        tailscale_service.connect(logs.ts, ts_token)
        ts_token = ""

    username = Path.home().name
    if ssh_pwd_cfg:
        ssh_pwd = ssh_pwd_cfg
        logger.info("Setting SSH password from Hugging Face Secrets (PASS)...")
    else:
        ssh_pwd = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        logger.success(f"Generated SSH Password for '{username}': {ssh_pwd}")
    ssh_pwd_cfg = ""

    try:
        subprocess.run(
            ["sudo", "/usr/sbin/chpasswd"],
            input=f"{username}:{ssh_pwd}\n",
            text=True,
            check=True,
        )
    except Exception as e:
        logger.error(f"Failed to set password: {e}")
    ssh_pwd = ""

    subprocess.Popen(
        "sudo /usr/sbin/sshd -D", shell=True, stdout=logs.ts, stderr=logs.ts
    )

    if "playit" in enabled:
        if not wait_for_port(LOCALHOST, PORTS["ssh"], timeout=30):
            logger.error(f"SSH daemon did not become ready on port {PORTS['ssh']}")
        else:
            logger.info(f"SSH daemon ready on port {PORTS['ssh']}")
            playit_service.start_xor_bridge()

    if "minecraft" in enabled:
        from services import minecraft_service

        minecraft_service.start()

    if "llm_proxy" in enabled:
        from services import llm_proxy_service

        llm_proxy_service.start(logs.llm_proxy)

    if "open_webui" in enabled:
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

    if "gradio" in enabled and "gradio_proc" in locals():
        gradio_proc.wait()
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down orchestrator...")


if __name__ == "__main__":
    main()
