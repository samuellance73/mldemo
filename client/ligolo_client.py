import os
import shutil
import subprocess
import sys

from client import common
from client.chisel_client import run_chisel_client
from client.gost_client import run_gost_client

CACHE_DIR = os.path.expanduser("~/.cache/sanctuary/ligolo")
HUB_MESH_PATH = "/tensor-mesh"
WEB_UI_PORT = 6801


def _cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def hub_connect_url(hf_url):
    return hf_url.rstrip("/") + HUB_MESH_PATH


def _fingerprint_cache(node_name):
    return _cache_path(f"{node_name}_fingerprint.txt")


def load_fingerprint(node_name):
    path = _fingerprint_cache(node_name)
    if os.path.isfile(path):
        return open(path).read().strip()
    return None


def save_fingerprint(node_name, fp):
    with open(_fingerprint_cache(node_name), "w") as f:
        f.write(fp.strip() + "\n")


def fetch_fingerprint_ssh(ssh_port=2222):
    """Read fingerprint file from container via local forwarded SSH.
    
    Returns a tuple (fingerprint, error_msg).
    """
    cmd = [
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
        "cat",
        "/home/user/.torch_metrics/ligolo_fingerprint.txt",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            stdout_clean = r.stdout.strip()
            if stdout_clean:
                fp = stdout_clean.splitlines()[0].strip()
                return fp, None
            else:
                return None, "File is empty"
        else:
            err = r.stderr.strip() or f"SSH exited with code {r.returncode}"
            return None, err
    except subprocess.TimeoutExpired:
        return None, "SSH command timed out (15s)"
    except OSError as e:
        return None, f"OS error running SSH: {e}"


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
                common.log_info("Ensure the tunnel is active and the remote service has started.")

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
    remotes = local_forward
    if via == "chisel":
        run_chisel_client(hf_url, remotes if isinstance(remotes, str) else " ".join(remotes))
    elif via == "gost":
        ssh = False
        proxy = False
        lf = local_forward
        run_gost_client(hf_url, auth, ssh, proxy, lf, ssh_fn, transport)
    else:
        common.log_error(f"Unknown tunnel via={via}")
        sys.exit(1)
