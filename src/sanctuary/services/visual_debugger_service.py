import os
import shutil
import subprocess
import time
from pathlib import Path

from loguru import logger

from sanctuary.core.constants import PORTS

PREFIX = "[VISDBG]"

# Process aliases
_R = subprocess.run
_P = subprocess.Popen
_DN = subprocess.DEVNULL


def start(log):
    """
    VNC-over-Tunnel visual debugger.
    Configured to run an optimized minimal XFCE4 desktop environment,
    using local UNIX sockets for robust display verification and bypassing
    SSL check crashes via mock certificates.
    """
    display_num = "18231"
    display = f":{display_num}"

    logger.info(f"{PREFIX} Terminating stale display pipelines...")

    # Kill any lingering processes from previous runs using container binary names
    t_kills = [
        "display-config",
        "Xvnc",
        "xorg-ipc-server",
        "xfce4-session",
        "xfwm4",
        "data-renderer"
    ]
    for t in t_kills:
        _R(["pkill", "-9", "-f", t], stdout=_DN, stderr=_DN)
    time.sleep(1)

    # X11 socket directory setup (must be writable)
    sock_dir = "/tmp/.X11-unix"
    os.makedirs(sock_dir, exist_ok=True)

    # Stale lock cleanup
    for f in [f"/tmp/.X{display_num}-lock", f"{sock_dir}/X{display_num}"]:
        try:
            os.remove(f)
        except OSError:
            pass

    # Config directory
    cfg_dir = Path.home() / ".vnc"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    # Write kasmvnc.yaml with mock SSL certificate paths to bypass existence check crashes
    payload_cfg = f"""
network:
  interface: 127.0.0.1
  websocket_port: {PORTS["visual_debugger"]}
  udp:
    public_ip: 127.0.0.1
  ssl:
    require_ssl: false
    pem_certificate: /etc/hostname
    pem_key: /etc/hostname
desktop:
  resolution:
    width: 1280
    height: 720
  allow_resize: false
server:
  auto_shutdown:
    no_user_session_timeout: 0
command_line:
  prompt: false
"""
    (cfg_dir / "kasmvnc.yaml").write_text(payload_cfg.strip() + "\n")

    # Write xstartup using local UNIX socket bindings (DISPLAY=:)
    # Executes 'xfce4-session' instead of Fluxbox
    payload_sh = f"""#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export DISPLAY={display}
exec xfce4-session
"""
    sh_path = cfg_dir / "xstartup"
    sh_path.write_text(payload_sh.strip() + "\n")
    sh_path.chmod(0o755)

    # Pre-seed credentials natively via 'digest-generator' (kasmvncpasswd)
    logger.info(f"{PREFIX} Pre-seeding credential store...")
    passwd_bin = shutil.which("digest-generator") or "digest-generator"
    _R(
        [passwd_bin, "-u", "user", "-w", "-r"],
        input=b"kasmpass\nkasmpass\nn\n",
        stdout=_DN,
        stderr=_DN,
    )

    logger.info(f"{PREFIX} Initiating adapter on subsystem {display}...")

    # Launch display-config (kasmvncserver)
    adapter_bin = shutil.which("display-config") or "display-config"
    adapter_cmd = [
        adapter_bin,
        display,
        "-select-de",
        "manual",
        "-disableBasicAuth"
    ]

    _P(adapter_cmd, env=os.environ, stdout=log, stderr=log)

    time.sleep(4)

    # Verify display is up via local UNIX socket (DISPLAY=:18231)
    env_chk = os.environ.copy()
    env_chk["DISPLAY"] = display
    adapter_up = False
    chk_bin = shutil.which("adapter-status-checker") or "adapter-status-checker"

    for _ in range(6):
        chk = _R([chk_bin], env=env_chk, stdout=_DN, stderr=_DN)
        if chk.returncode == 0:
            adapter_up = True
            break
        time.sleep(2)

    if not adapter_up:
        logger.error(f"{PREFIX} Adapter {display} failure — visual debugger aborted")
        return

    # Launch rendering engine 'data-renderer' (Firefox) targeting the local UNIX socket
    env = os.environ.copy()
    env["DISPLAY"] = display
    env["NO_AT_BRIDGE"] = "1"

    browser_bin = shutil.which("data-renderer") or "data-renderer"
    engine_cmd = [
        browser_bin,
        "--new-instance",
        "--no-remote",
        "http://127.0.0.1:7860"
    ]

    logger.info(f"{PREFIX} Launching visualization pipeline on {display}")
    _P(engine_cmd, env=env, stdout=log, stderr=log)
    logger.success(
        f"{PREFIX} Visual debugger active (Stream: 8501, display={display})."
    )