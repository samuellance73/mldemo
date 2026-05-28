import subprocess
import sys
from pathlib import Path

from client import common
from client.chisel_client import run_chisel_client
from client.gost_client import run_gost_client

CACHE_DIR = Path("~/.cache/sanctuary/ligolo").expanduser()
HUB_MESH_PATH = "/tensor-mesh"
WEB_UI_PORT = 6801


def _cache_path(name):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def hub_connect_url(hf_url):
    return hf_url.rstrip("/") + HUB_MESH_PATH


def _fingerprint_cache(node_name):
    return _cache_path(f"{node_name}_fingerprint.txt")


def load_fingerprint(node_name):
    path = _fingerprint_cache(node_name)
    if path.is_file():
        return path.read_text().strip()
    return None


def save_fingerprint(node_name, fp):
    _fingerprint_cache(node_name).write_text(fp.strip() + "\n")


# One-liner run inside the container: performs a TLS handshake against the
# local ligolo listener and prints the SHA-256 of the DER-encoded cert.
_TLS_FP_CMD = (
    "python3 -c "
    "'import ssl, socket, hashlib; "
    "ctx = ssl.create_default_context(); "
    "ctx.check_hostname = False; "
    "ctx.verify_mode = ssl.CERT_NONE; "
    's = socket.create_connection(("127.0.0.1", 11601)); '
    "ss = ctx.wrap_socket(s); "
    "print(hashlib.sha256(ss.getpeercert(binary_form=True)).hexdigest().upper())'"
)


def fetch_fingerprint_ssh(ssh_port=2222):
    """Fetch the ligolo TLS fingerprint from the container.

    Primary method: direct TLS handshake against port 11601 via SSH remote
    command.  This works even when Ligolo skips printing the fingerprint on
    subsequent boots (cert already cached on disk, so no log line is emitted).

    Fallback: read the pre-written fingerprint file (works on first boot when
    the log scraper succeeds).

    Returns a tuple (fingerprint_hex_upper, error_msg).
    """
    ssh_base = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=10",
        "user@127.0.0.1",
        "-p",
        str(ssh_port),
    ]

    # --- Primary: live TLS handshake ---
    try:
        r = subprocess.run(
            ssh_base + [_TLS_FP_CMD],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            line = r.stdout.strip().splitlines()[-1].strip()
            if len(line) == 64 and all(c in "0123456789ABCDEFabcdef" for c in line):
                return line.upper(), None
        tls_err = r.stderr.strip() or f"SSH exited {r.returncode}"
    except subprocess.TimeoutExpired:
        tls_err = "TLS handshake SSH timed out (15s)"
    except OSError as e:
        tls_err = f"OS error (TLS path): {e}"

    # --- Fallback: log-scraped fingerprint file ---
    try:
        r = subprocess.run(
            ssh_base + ["cat", "/home/user/.torch_metrics/ligolo_fingerprint.txt"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            stdout_clean = r.stdout.strip()
            if stdout_clean:
                return stdout_clean.splitlines()[0].strip(), None
            return None, "Fingerprint file is empty"
        file_err = r.stderr.strip() or f"SSH exited {r.returncode}"
    except subprocess.TimeoutExpired:
        file_err = "file-read SSH timed out (15s)"
    except OSError as e:
        file_err = f"OS error (file path): {e}"

    return None, f"TLS handshake failed ({tls_err}); file fallback failed ({file_err})"


def print_hub_info(hf_url, node_name, fingerprint=None, fetch=False):
    connect_url = hub_connect_url(hf_url)
    fp = fingerprint or load_fingerprint(node_name)
    agent_name = "inference-edge-worker"

    if fetch:
        common.log_info("Fetching fingerprint via SSH (port 2222 must be forwarded)...")
        fetched_fp, err = fetch_fingerprint_ssh()
        if fetched_fp:
            common.log_info(f"[+] Successfully fetched fingerprint: {fetched_fp}")
            save_fingerprint(node_name, fetched_fp)
            fp = fetched_fp
        else:
            common.log_error(f"[-] Failed to fetch fingerprint: {err}")
            if fp:
                common.log_info(f"[*] Falling back to cached fingerprint: {fp}")
            else:
                common.log_info(
                    "Ensure the tunnel is active and the remote service has started."
                )

    print("====================================================================")
    print("                 LIGOLO HUB — AGENT CONNECT")
    print("====================================================================")
    print(f"  Node URL:     {hf_url}")
    print(f"  Agent C2:     {connect_url}")
    print(f"  Web UI path:  {hf_url.rstrip('/')}/routing-console")
    print()
    if fp:
        print(f"  {agent_name} -connect {connect_url} -accept-fingerprint {fp}")
    else:
        print(f"  {agent_name} -connect {connect_url} -ignore-cert")
        print("  (no fingerprint cached; use -accept-fingerprint after proxy starts)")
    print()
    print("  Operator: forward Web UI with chisel/gost, e.g.")
    print(
        f"    cc.py ligolo hub --node {node_name} --via chisel "
        f"-L {WEB_UI_PORT}:127.0.0.1:{WEB_UI_PORT}"
    )
    print("====================================================================")


def run_hub_forward(hf_url, via, local_forward, auth, transport, ssh_fn):
    if not local_forward:
        common.log_error("Hub forward requires -L local:remote:port")
        sys.exit(1)
    if via == "chisel":
        remotes = (
            local_forward if isinstance(local_forward, str) else " ".join(local_forward)
        )
        run_chisel_client(hf_url, remotes)
    elif via == "gost":
        run_gost_client(hf_url, auth, False, False, local_forward, ssh_fn, transport)
    else:
        common.log_error(f"Unknown tunnel via={via}")
        sys.exit(1)
