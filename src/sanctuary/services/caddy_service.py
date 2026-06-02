import os
import shutil
import subprocess
from pathlib import Path

from sanctuary.core.constants import (
    CADDYFILE_PATH,
    CADDYFILE_TEMPLATE_PATH,
    LOADING_HTML_PATH,
    METRICS_DIR,
    PORTS,
    STATIC_DIR,
)
from loguru import logger

from sanctuary.common.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


def start(caddy_log):
    logger.info(f"Enabling Caddy smart frontend on port {PORTS['caddy']}...")

    try:
        static_dir = STATIC_DIR
        if not static_dir.is_dir():
            static_dir = Path("static")
        static_dir.mkdir(parents=True, exist_ok=True)

        src_loading_paths = [
            LOADING_HTML_PATH,
            Path("config/loading.html"),
            Path("main/config/loading.html"),
        ]
        copied = False
        for path in src_loading_paths:
            if path.exists():
                shutil.copy(path, static_dir / "loading.html")
                copied = True
                break
        if not copied:
            logger.warning("Could not find loading.html to copy to static directory.")
    except Exception as e:
        logger.error(f"Failed to copy loading.html to static directory: {e}")

    caddy_conf = None
    template_paths = [
        CADDYFILE_TEMPLATE_PATH,
        Path("config/Caddyfile.template"),
        Path("main/config/Caddyfile.template"),
    ]
    for path in template_paths:
        try:
            if path.exists():
                caddy_conf = path.read_text()
                break
        except Exception:
            pass

    if caddy_conf is None:
        logger.error("Failed to prepare caddy config: Caddyfile.template not found.")
        return

    substitutions = {
        "{METRICS_DIR}": str(METRICS_DIR),
        "{STATIC_DIR}": str(STATIC_DIR),
        "{LOCALHOST}": "127.0.0.1",
        "{CADDY_PORT}": str(PORTS["caddy"]),
        "{CADDY_SECONDARY_PORT}": str(PORTS["caddy_secondary"]),
        "{CHISEL_PORT}": str(PORTS["chisel"]),
        "{GOST_PORT}": str(PORTS["gost"]),
        "{MODEL_SYNC_PORT}": str(PORTS["model_sync"]),
        "{SLIVER_PORT}": str(PORTS["sliver"]),
        "{LLM_PROXY_PORT}": str(PORTS["llm_proxy"]),
        "{FILEBROWSER_PORT}": str(PORTS["filebrowser"]),
        "{GRADIO_PORT}": str(PORTS["gradio"]),
    }

    for placeholder, value in substitutions.items():
        caddy_conf = caddy_conf.replace(placeholder, value)

    try:
        out_paths = [CADDYFILE_PATH, Path("Caddyfile")]
        written = False
        for path in out_paths:
            try:
                dir_path = path.resolve().parent
                if dir_path.is_dir() and os.access(dir_path, os.W_OK):
                    path.write_text(caddy_conf)
                    written = True
                    break
            except Exception:
                pass

        if not written:
            raise PermissionError("Could not write Caddyfile to any expected path.")
    except Exception as e:
        logger.error(f"Failed to prepare caddy config: {e}")
        return

    caddy_log.write("[*] Testing caddy configuration...\n")
    caddy_log.flush()
    cmd_caddy_test = decode_cmd(
        harden(
            f"model-routing-engine validate --config {CADDYFILE_PATH} --adapter caddyfile"
        )
    )
    subprocess.run(
        cmd_caddy_test, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT
    )

    caddy_log.write("[*] Starting caddy daemon...\n")
    caddy_log.flush()
    cmd_caddy = decode_cmd(
        harden(
            f"model-routing-engine run --config {CADDYFILE_PATH} --adapter caddyfile"
        )
    )
    subprocess.Popen(cmd_caddy, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT)
