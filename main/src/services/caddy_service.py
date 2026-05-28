import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger

from .utils import decode_cmd


def start(caddy_log):
    logger.info("Enabling Caddy smart frontend on port 7860...")

    # 1. Prepare static directory and copy loading.html
    try:
        static_dir = Path("/home/user/static")
        if not static_dir.is_dir():
            static_dir = Path("static")
        static_dir.mkdir(parents=True, exist_ok=True)

        src_loading_paths = [
            Path("/home/user/config/loading.html"),
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

    # 2. Find and read Caddyfile.template
    caddy_conf = None
    template_paths = [
        Path("/home/user/config/Caddyfile.template"),
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

    # 3. Write Caddyfile output
    try:
        out_paths = [Path("/home/user/Caddyfile"), Path("Caddyfile")]
        written = False
        for path in out_paths:
            try:
                # Check if we can write to directory
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
        OBFUSCATE(
            "model-routing-engine validate --config /home/user/Caddyfile --adapter caddyfile"
        )
    )
    subprocess.run(
        cmd_caddy_test, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT
    )

    caddy_log.write("[*] Starting caddy daemon...\n")
    caddy_log.flush()
    cmd_caddy = decode_cmd(
        OBFUSCATE(
            "model-routing-engine run --config /home/user/Caddyfile --adapter caddyfile"
        )
    )
    subprocess.Popen(cmd_caddy, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT)
