import re
import subprocess
import threading
import time
from pathlib import Path

from loguru import logger

from sanctuary.core.constants import METRICS_DIR, PORTS
from sanctuary.common.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


# Where the extracted public tunnel URL is written for other services to read.
TUNNEL_URL_PATH = METRICS_DIR / "cloudflare_url.txt"

# Matches quick-tunnel ephemeral URLs printed by cloudflared.
_URL_RE = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", re.IGNORECASE)


def _extract_tunnel_url(log_path, out_path, stop_event):
    """Tail the cloudflared log file until the public URL appears, then persist it."""
    deadline = time.time() + 120
    log_path_obj = Path(log_path)
    while time.time() < deadline and not stop_event.is_set():
        try:
            if not log_path_obj.exists():
                time.sleep(1)
                continue
            with log_path_obj.open("r", errors="replace") as f:
                text = f.read()
            m = _URL_RE.search(text)
            if m:
                url = m.group(0)
                Path(out_path).write_text(url + "\n")
                logger.success("Cloudflare quick-tunnel URL: {}", url)
                return
        except OSError:
            pass
        time.sleep(2)
    logger.warning("Cloudflare tunnel URL not detected within timeout.")


def start(cf_log, token=""):
    """Start cloudflared tunnel.

    Named tunnel (token provided):
        Requires a Cloudflare account + pre-created tunnel.  The tunnel's
        hostname is configured in the Cloudflare dashboard so no URL extraction
        is needed.

    Quick tunnel (no token):
        Ephemeral public HTTPS URL printed to stdout, no account required.
        Exposes Caddy on :{PORTS['caddy']}.  A background thread extracts and
        persists the URL to TUNNEL_URL_PATH.
    """
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    if TUNNEL_URL_PATH.exists():
        TUNNEL_URL_PATH.unlink()

    if token:
        cf_log.write(
            "[*] Starting Cloudflare named tunnel (token auth, persistent hostname)...\n"
        )
        cf_log.flush()
        cmd_base = decode_cmd(
            harden("nice -n 19 edge-cache-relay tunnel --no-autoupdate run --token ")
        )
        cmd = f"{cmd_base}{token}"
        token = ""  # wipe local copy immediately
        subprocess.Popen(cmd, shell=True, stdout=cf_log, stderr=subprocess.STDOUT)
        # Named tunnels use a pre-configured domain — no URL extraction required.
    else:
        cf_log.write(
            f"[*] Starting Cloudflare quick tunnel (ephemeral URL, no account) "
            f"-> http://localhost:{PORTS['caddy']}...\n"
        )
        cf_log.flush()
        cmd = decode_cmd(
            harden(
                f"nice -n 19 edge-cache-relay tunnel --no-autoupdate"
                f" --url http://localhost:{PORTS['caddy']}"
            )
        )
        subprocess.Popen(cmd, shell=True, stdout=cf_log, stderr=subprocess.STDOUT)

        stop = threading.Event()
        threading.Thread(
            target=_extract_tunnel_url,
            args=(str(METRICS_DIR / "cloudflare.log"), TUNNEL_URL_PATH, stop),
            daemon=True,
        ).start()
