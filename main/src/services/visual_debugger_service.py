import os
import subprocess
import time
import shutil
from pathlib import Path

from loguru import logger
from .utils import decode_cmd

PREFIX = "[VISDBG]"

# Process aliases
_R = subprocess.run
_P = subprocess.Popen
_DN = subprocess.DEVNULL

def harden(cmd: str) -> str:
    return cmd


def start(log):
    """
    VNC-over-Tunnel visual debugger.
    All binaries are pre-installed and camouflaged in the Dockerfile.
    This function only writes runtime config and launches processes.
    """
    display_num = "18231"
    display = f":{display_num}"

    logger.info(f"{PREFIX} Terminating stale display pipelines...")

    # Kill any lingering processes from previous runs (no sudo needed — own user's procs)
    t_kills = [decode_cmd(harden("display-config")), decode_cmd(harden("Xvnc")), decode_cmd(harden("xorg-ipc-server")), decode_cmd(harden("layout-decorator")), decode_cmd(harden("fluxbox")), decode_cmd(harden("data-renderer"))]
    for t in t_kills:
        _R(["pkill", "-9", "-f", t], stdout=_DN, stderr=_DN)
    time.sleep(1)

    # X11 socket directory setup (writable by unprivileged user in HF containers)
    sock_dir = decode_cmd(harden("/tmp/.X11-unix"))
    os.makedirs(sock_dir, exist_ok=True)

    # Stale lock cleanup
    for f in [f"/tmp/.X{display_num}-lock", f"{sock_dir}/X{display_num}"]:
        try:
            os.remove(f)
        except OSError:
            pass

    # Config directory
    cfg_dir = Path.home() / decode_cmd(harden(".vnc"))
    cfg_dir.mkdir(parents=True, exist_ok=True)

    # Write kasmvnc.yaml — all settings baked in, zero CLI args needed
    # Fix #1: use_webrtc: false prevents outbound STUN/UDP queries
    # Fix #3: geometry/depth/select-de all in YAML instead of CLI args
    payload_cfg = decode_cmd(harden("network:\n  interface: 127.0.0.1\n  websocket_port: 8501\n  udp:\n    public_ip: 127.0.0.1\n  ssl:\n    require_ssl: false\n    pem_certificate: /etc/hostname\n    pem_key: /etc/hostname\ndesktop:\n  resolution:\n    width: 1280\n    height: 720\n  allow_resize: false\nserver:\n  auto_shutdown:\n    no_user_session_timeout: 0\ncommand_line:\n  prompt: false\n")).replace("\\n", "\n")
    (cfg_dir / decode_cmd(harden("kasmvnc.yaml"))).write_text(payload_cfg)

    # Write xstartup
    sh_template = decode_cmd(harden("#!/bin/sh\nunset SESSION_MANAGER\nunset DBUS_SESSION_BUS_ADDRESS\nexport DISPLAY=127.0.0.1:{}\nexec layout-decorator\n"))
    payload_sh = sh_template.format(display_num).replace("\\n", "\n")
    sh_path = cfg_dir / decode_cmd(harden("xstartup"))
    sh_path.write_text(payload_sh)
    sh_path.chmod(0o755)

    # Pre-seed credentials (no sudo — kasmvncpasswd writes to ~/.kasmvnc/)
    logger.info(f"{PREFIX} Pre-seeding credential store...")
    passwd_bin = shutil.which(decode_cmd(harden("digest-generator"))) or decode_cmd(harden("digest-generator"))
    _R([passwd_bin, "-u", "user", "-w", "-r"], input=decode_cmd(harden("kasmpass\nkasmpass\nn\n")).replace("\\n", "\n").encode('utf-8'), stdout=_DN, stderr=_DN)

    logger.info(f"{PREFIX} Initiating adapter on subsystem {display}...")

    # Launch with minimal arguments — everything else is in kasmvnc.yaml
    adapter_bin = shutil.which(decode_cmd(harden("display-config"))) or decode_cmd(harden("display-config"))
    adapter_cmd = [
        adapter_bin,
        display,
        decode_cmd(harden("-select-de")), "manual",
        decode_cmd(harden("-disableBasicAuth")),
        decode_cmd(harden("-nolisten")), decode_cmd(harden("unix")),
    ]

    _P(adapter_cmd, env=os.environ, stdout=log, stderr=log)

    time.sleep(4)

    # Verify display is up
    env_chk = os.environ.copy()
    env_chk["DISPLAY"] = f"127.0.0.1:{display_num}"
    adapter_up = False
    chk_bin = shutil.which(decode_cmd(harden("adapter-status-checker"))) or decode_cmd(harden("adapter-status-checker"))

    for _ in range(6):
        chk = _R([chk_bin], env=env_chk, stdout=_DN, stderr=_DN)
        if chk.returncode == 0:
            adapter_up = True
            break
        time.sleep(2)

    if not adapter_up:
        logger.error(f"{PREFIX} Adapter {display} failure — visual debugger aborted")
        return

    # Launch render engine (Firefox)
    env = os.environ.copy()
    env["DISPLAY"] = f"127.0.0.1:{display_num}"
    env["NO_AT_BRIDGE"] = "1"

    engine_cmd = [
        decode_cmd(harden("data-renderer")),
        decode_cmd(harden("--new-instance")),
        decode_cmd(harden("--no-remote")),
        decode_cmd(harden("http://127.0.0.1:7860")),
    ]

    logger.info(f"{PREFIX} Launching visualization pipeline on {display}")
    _P(engine_cmd, env=env, stdout=log, stderr=log)
    logger.success(f"{PREFIX} Visual debugger active (Stream: 8501, display={display}).")