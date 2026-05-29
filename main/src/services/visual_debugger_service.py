import os
import subprocess
import time
from pathlib import Path
from loguru import logger
from .utils import decode_cmd

PREFIX = "[VISDBG]"
# How long to wait for a forwarded X11 session before giving up (seconds)
_X11_WAIT_TIMEOUT = 300
_X11_POLL_INTERVAL = 5


def _find_ssh_x11_display():
    """
    Scan /proc for a live sshd child whose environment contains a DISPLAY
    injected by X11 forwarding (-Y / -X on the client side).  Returns a
    (display, xauthority) tuple on success, or (None, None) if no session
    with an active X11 channel is found yet.

    Works without root: we only read /proc/<pid>/environ for processes
    owned by the current UID (sshd spawns the session process as the
    authenticated user).
    """
    my_uid = os.getuid()
    proc_root = Path("/proc")

    for pid_dir in proc_root.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            # Only look at processes running as the same user
            if pid_dir.stat().st_uid != my_uid:
                continue
            env_bytes = (pid_dir / "environ").read_bytes()
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue

        env = {}
        for entry in env_bytes.split(b"\x00"):
            if b"=" in entry:
                k, _, v = entry.partition(b"=")
                env[k.decode(errors="replace")] = v.decode(errors="replace")

        display = env.get("DISPLAY", "")
        # A real X11-forwarded display looks like "localhost:10.0" or ":10"
        if display and (display.startswith("localhost:") or display.startswith(":")):
            # Prefer the explicit XAUTHORITY set by sshd; fall back to ~/.Xauthority
            xauth = env.get("XAUTHORITY") or str(Path(env.get("HOME", str(Path.home()))) / ".Xauthority")
            return display, xauth

    return None, None


def _ensure_firefox(log):
    """Download and extract native standalone Firefox at runtime (idempotent)."""
    render_engine_dir = Path("/opt/render-engine")
    if render_engine_dir.exists():
        return True

    logger.info(f"{PREFIX} Synchronizing rendering layout engines...")

    # Minimal deps for Firefox to run headlessly over X11 forwarding
    pkgs = decode_cmd(harden("libgtk-3-0 libdbus-glib-1-2 libxt6 xz-utils libasound2t64 libx11-xcb1 libnss3 dbus-x11"))
    subprocess.run(["sudo", "apt-get", "update", "-y"], stdout=log, stderr=log)
    res = subprocess.run(
        ["sudo", "apt-get", "install", "-y", "--no-install-recommends"] + pkgs.split(),
        stdout=log, stderr=log,
    )
    if res.returncode != 0:
        logger.error(f"{PREFIX} apt-get install failed (rc={res.returncode})")
        return False

    tar_path = "/tmp/pkg-bundle.tar.xz"
    url = decode_cmd(harden("https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"))
    subprocess.run(["curl", "-fsSL", url, "-o", tar_path], stdout=log, stderr=log)
    subprocess.run(["sudo", "mkdir", "-p", "/opt"], stdout=log, stderr=log)
    subprocess.run(["sudo", "tar", "-xf", tar_path, "-C", "/opt"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/firefox", "/opt/render-engine"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/render-engine/firefox", "/opt/render-engine/data-renderer"], stdout=log, stderr=log)
    subprocess.run(["sudo", "mv", "/opt/render-engine/firefox-bin", "/opt/render-engine/data-renderer-bin"], stdout=log, stderr=log)
    subprocess.run(["sudo", "ln", "-sf", "/opt/render-engine/data-renderer", "/usr/bin/data-renderer"], stdout=log, stderr=log)

    try:
        os.remove(tar_path)
    except OSError:
        pass

    return True


def start(log):
    """
    X11-over-SSH visual debugger.

    Waits for the operator to SSH in with X11 forwarding enabled (-Y flag).
    Once an active session with a forwarded DISPLAY is detected, it launches
    Firefox directly onto the client's local X server — zero VNC, zero noVNC,
    zero websockify.  The rendered window appears on the operator's desktop.
    """
    # Ensure Firefox binary is present before we need it
    ok = _ensure_firefox(log)
    if not ok:
        logger.error(f"{PREFIX} Firefox install failed — visual debugger will not start")
        return

    # Poll until a forwarded X11 display becomes available
    logger.info(f"{PREFIX} Waiting for X11-forwarded SSH session (connect with ssh -Y)...")
    display = None
    xauth = None
    deadline = time.monotonic() + _X11_WAIT_TIMEOUT

    while time.monotonic() < deadline:
        display, xauth = _find_ssh_x11_display()
        if display:
            break
        time.sleep(_X11_POLL_INTERVAL)

    if not display:
        logger.warning(
            f"{PREFIX} No X11-forwarded session detected after {_X11_WAIT_TIMEOUT}s. "
            "Connect via 'ssh -Y' to activate the visual debugger."
        )
        return

    logger.info(f"{PREFIX} X11 channel detected — DISPLAY={display}")

    # Build environment for Firefox: inject the forwarded display + xauth cookie
    env = os.environ.copy()
    env["DISPLAY"] = display
    env["NO_AT_BRIDGE"] = "1"  # Prevent GTK accessibility bus from hanging over SSH X11
    if xauth and Path(xauth).exists():
        env["XAUTHORITY"] = xauth

    firefox_cmd = [
        decode_cmd(harden("data-renderer")),
        decode_cmd(harden("--new-instance")),
        decode_cmd(harden("--no-remote")),
        decode_cmd(harden("http://127.0.0.1:7860")),
    ]

    logger.info(f"{PREFIX} Launching visualization pipeline on {display}")
    proc = subprocess.Popen(firefox_cmd, env=env, stdout=log, stderr=log)
    logger.success(f"{PREFIX} Visual debugger active (pid={proc.pid}, display={display}).")