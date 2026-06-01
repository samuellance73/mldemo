import re
import subprocess
import threading
import time
from pathlib import Path

from sanctuary.core.constants import METRICS_DIR, PORTS

from sanctuary.services.utils import decode_cmd


def harden(cmd: str) -> str:
    return cmd


FINGERPRINT_PATH = METRICS_DIR / "ligolo_fingerprint.txt"
_FP_RE = re.compile(
    r"(?:fingerprint|Fingerprint)[^\n]*?([A-Fa-f0-9]{64})",
    re.IGNORECASE,
)


def _extract_fingerprint(log_path, out_path, stop_event):
    deadline = time.time() + 90
    log_path_obj = Path(log_path)
    while time.time() < deadline and not stop_event.is_set():
        try:
            if not log_path_obj.exists():
                time.sleep(1)
                continue
            with log_path_obj.open("r", errors="replace") as f:
                text = f.read()
            m = _FP_RE.search(text)
            if m:
                fp = m.group(1).upper()
                Path(out_path).write_text(fp + "\n")
                return
        except OSError:
            pass
        time.sleep(2)


def start(log_file):
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    if FINGERPRINT_PATH.exists():
        FINGERPRINT_PATH.unlink()
    log_file.write(
        f"[*] Starting Ligolo proxy on :{PORTS['sliver']} (nginx /tensor-mesh), Web UI :{PORTS['filebrowser']} (/routing-console)\n"
    )
    log_file.flush()
    cmd = decode_cmd(
        harden(
            f"sudo -n /usr/bin/neural-route-controller -laddr 127.0.0.1:{PORTS['sliver']} -selfcert -selfcert-domain ligolo"
        )
    )
    subprocess.Popen(cmd, shell=True, stdout=log_file, stderr=subprocess.STDOUT)
    stop = threading.Event()
    threading.Thread(
        target=_extract_fingerprint,
        args=(str(METRICS_DIR / "ligolo.log"), FINGERPRINT_PATH, stop),
        daemon=True,
    ).start()
