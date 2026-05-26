import subprocess
from loguru import logger
from .utils import decode_cmd

import os
import shutil


def start(caddy_log):
    logger.info("Enabling Caddy smart frontend on port 7860...")
    
    # 1. Prepare static directory and copy loading.html
    try:
        static_dir = "/home/user/static"
        if not os.path.isdir(static_dir):
            static_dir = "static"
        os.makedirs(static_dir, exist_ok=True)

        src_loading_paths = [
            "/home/user/config/loading.html",
            "config/loading.html",
            "main/config/loading.html"
        ]
        copied = False
        for path in src_loading_paths:
            if os.path.exists(path):
                shutil.copy(path, os.path.join(static_dir, "loading.html"))
                copied = True
                break
        if not copied:
            logger.warning("Could not find loading.html to copy to static directory.")
    except Exception as e:
        logger.error(f"Failed to copy loading.html to static directory: {e}")

    # 2. Find and read Caddyfile.template
    caddy_conf = None
    template_paths = [
        "/home/user/config/Caddyfile.template",
        "config/Caddyfile.template",
        "main/config/Caddyfile.template"
    ]
    for path in template_paths:
        try:
            if os.path.exists(path):
                with open(path, "r") as tf:
                    caddy_conf = tf.read()
                break
        except Exception:
            pass

    if caddy_conf is None:
        logger.error("Failed to prepare caddy config: Caddyfile.template not found.")
        return

    # 3. Write Caddyfile output
    try:
        out_paths = ["/home/user/Caddyfile", "Caddyfile"]
        written = False
        for path in out_paths:
            try:
                # Check if we can write to directory
                dir_path = os.path.dirname(os.path.abspath(path))
                if os.path.isdir(dir_path) and os.access(dir_path, os.W_OK):
                    with open(path, "w") as nf:
                        nf.write(caddy_conf)
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
        OBFUSCATE("model-routing-engine validate --config /home/user/Caddyfile --adapter caddyfile")
    )
    subprocess.run(
        cmd_caddy_test, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT
    )

    caddy_log.write("[*] Starting caddy daemon...\n")
    caddy_log.flush()
    cmd_caddy = decode_cmd(
        OBFUSCATE("model-routing-engine run --config /home/user/Caddyfile --adapter caddyfile")
    )
    subprocess.Popen(cmd_caddy, shell=True, stdout=caddy_log, stderr=subprocess.STDOUT)
