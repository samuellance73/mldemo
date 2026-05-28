import os
import subprocess
from pathlib import Path
from loguru import logger
from .utils import decode_cmd

PORT = 6080
VNC_PORT = 5901
DISPLAY = ":1"
PREFIX = "[VISDBG]"


def start(log):
    """Launch a headless XFCE4 desktop with TigerVNC and websockify."""
    home = Path.home()
    vnc_dir = home / decode_cmd(OBFUSCATE(".vnc"))
    vnc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write the Xstartup file to initialize the XFCE session via dbus-launch
    xstartup_path = vnc_dir / decode_cmd(OBFUSCATE("xstartup"))
    xstartup_content = decode_cmd(OBFUSCATE("#!/bin/sh\nunset SESSION_MANAGER\nunset DBUS_SESSION_BUS_ADDRESS\n[ -x /etc/vnc/xstartup ] && exec /etc/vnc/xstartup\n[ -r $HOME/.Xresources ] && xrdb $HOME/.Xresources\nvncconfig -iconic &\nxsetroot -solid grey\ndbus-launch --exit-with-session startxfce4\n"))
    xstartup_path.write_text(xstartup_content)
    xstartup_path.chmod(0o755)

    # 2. Clean up any stale lock files from previous runs
    lock_a_prefix = decode_cmd(OBFUSCATE("/tmp/.X11-unix/X"))
    lock_b_prefix = decode_cmd(OBFUSCATE("/tmp/.X"))
    lock_b_suffix = decode_cmd(OBFUSCATE("-lock"))
    for lock in [f"{lock_a_prefix}{DISPLAY[1:]}", f"{lock_b_prefix}{DISPLAY[1:]}{lock_b_suffix}"]:
        try:
            p = Path(lock)
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.debug(f"{PREFIX} Cleanup warning: {e}")

    # 3. Start TigerVNC server on localhost only
    logger.info(f"{PREFIX} Starting VNC server on display {DISPLAY}...")
    vnc_cmd = [
        decode_cmd(OBFUSCATE("vncserver")),
        DISPLAY,
        decode_cmd(OBFUSCATE("-geometry")),
        decode_cmd(OBFUSCATE("1280x720")),
        decode_cmd(OBFUSCATE("-depth")),
        decode_cmd(OBFUSCATE("24")),
        decode_cmd(OBFUSCATE("-localhost")),
        decode_cmd(OBFUSCATE("yes")),
        decode_cmd(OBFUSCATE("-SecurityTypes")),
        decode_cmd(OBFUSCATE("None")),
    ]
    subprocess.run(vnc_cmd, stdout=log, stderr=log)

    # 4. Start Websockify to bridge standard browser traffic (WebSockets) to VNC
    logger.info(
        f"{PREFIX} Launching websockify on 127.0.0.1:{PORT} serving noVNC..."
    )
    # Ubuntu default location for noVNC HTML files is /usr/share/novnc/
    novnc_web = decode_cmd(OBFUSCATE("/usr/share/novnc/"))

    websockify_cmd = [
        decode_cmd(OBFUSCATE("websockify")),
        decode_cmd(OBFUSCATE("--web")),
        novnc_web,
        str(PORT),
        f"127.0.0.1:{VNC_PORT}",
    ]

    env = os.environ.copy()
    proc = subprocess.Popen(websockify_cmd, stdout=log, stderr=log, env=env)

    logger.success(
        f"{PREFIX} Visual debugger environment initiated (pid {proc.pid}). "
        f"Reachable at Caddy subpath /visual-debugger/vnc.html"
    )
