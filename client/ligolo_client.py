import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

from client import common
from client.chisel_client import run_chisel_client
from client.gost_client import run_gost_client

LIGOLO_VERSION = "0.8.3"
RELEASE_BASE = (
    f"https://github.com/nicocha30/ligolo-ng/releases/download/v{LIGOLO_VERSION}"
)

CACHE_DIR = os.path.expanduser("~/.cache/sanctuary/ligolo")
HUB_MESH_PATH = "/tensor-mesh"
WEB_UI_PORT = 6801
PROXY_PORT = 11601

_PROXY_CANDIDATES = (
    "LIGOLO_PROXY",
    "proxy",
    "ligolo-proxy",
    "ligolo-ng-proxy",
    "ligolo-ng_proxy",
)
_AGENT_CANDIDATES = (
    "LIGOLO_AGENT",
    "agent",
    "ligolo-agent",
    "ligolo-ng-agent",
    "ligolo-ng_agent",
)

_proxy_override = None
_agent_override = None


def set_bins(proxy_bin=None, agent_bin=None):
    global _proxy_override, _agent_override
    _proxy_override = proxy_bin
    _agent_override = agent_bin


def _cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def _which_candidates(names):
    for name in names:
        if name.isupper() or name.startswith("LIGOLO_"):
            env = os.environ.get(name)
            if env and os.path.isfile(env) and os.access(env, os.X_OK):
                return env
            continue
        path = shutil.which(name)
        if path:
            return path
    return None


def resolve_binary(kind, explicit=None, allow_download=True):
    """Resolve proxy or agent binary: explicit flag > env/PATH > cache > download."""
    if kind == "proxy":
        if explicit:
            return explicit
        if _proxy_override:
            return _proxy_override
        found = _which_candidates(_PROXY_CANDIDATES)
        if found:
            common.log_info(f"Using local proxy: {found}")
            return found
    else:
        if explicit:
            return explicit
        if _agent_override:
            return _agent_override
        found = _which_candidates(_AGENT_CANDIDATES)
        if found:
            common.log_info(f"Using local agent: {found}")
            return found

    if not allow_download:
        return "agent" if kind == "agent" else "proxy"

    return _download_binary(kind)


def _platform_asset(kind):
    """kind: 'proxy' or 'agent'"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    arch = arch_map.get(machine)
    if not arch:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    if system == "linux":
        return f"ligolo-ng_{kind}_{LIGOLO_VERSION}_linux_{arch}.tar.gz", "tar.gz"
    if system == "darwin":
        return f"ligolo-ng_{kind}_{LIGOLO_VERSION}_darwin_{arch}.tar.gz", "tar.gz"
    if system == "windows":
        return f"ligolo-ng_{kind}_{LIGOLO_VERSION}_windows_{arch}.zip", "zip"
    raise RuntimeError(f"Unsupported OS: {system}")


def _download_binary(kind):
    asset, fmt = _platform_asset(kind)
    dest = _cache_path(asset)
    bin_name = "proxy" if kind == "proxy" else "agent"
    out_bin = _cache_path(f"ligolo-{kind}-{platform.system().lower()}")

    if os.path.isfile(out_bin) and os.access(out_bin, os.X_OK):
        return out_bin

    path_hint = "proxy/agent on PATH, or set LIGOLO_PROXY / LIGOLO_AGENT"
    common.log_info(f"No local {kind} found ({path_hint}); downloading release asset")

    if not os.path.isfile(dest):
        url = f"{RELEASE_BASE}/{asset}"
        common.log_info(f"Downloading {url}")
        curl_cmd = ["curl", "-fsSL", "-o", dest, url]
        try:
            subprocess.run(curl_cmd, check=True, timeout=300)
        except subprocess.CalledProcessError:
            common.log_info("Retrying download with curl -k (SSL verify off)")
            try:
                subprocess.run(
                    ["curl", "-kfsSL", "-o", dest, url], check=True, timeout=300
                )
            except (subprocess.CalledProcessError, OSError, FileNotFoundError) as e:
                common.log_error(f"Download failed: {e}")
                sys.exit(1)
        except (OSError, FileNotFoundError) as e:
            common.log_error(f"Download failed: {e}")
            sys.exit(1)

    if fmt == "tar.gz":
        with tarfile.open(dest, "r:gz") as tf:
            tf.extractall(path=CACHE_DIR)
    else:
        with zipfile.ZipFile(dest, "r") as zf:
            zf.extractall(CACHE_DIR)

    extracted = os.path.join(CACHE_DIR, bin_name)
    if not os.path.isfile(extracted):
        common.log_error(f"Expected {extracted} after extract")
        sys.exit(1)
    shutil.copy2(extracted, out_bin)
    os.chmod(out_bin, 0o755)
    return out_bin


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
    """Read fingerprint file from container via local forwarded SSH."""
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
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0].strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def print_hub_info(hf_url, node_name, fingerprint=None, fetch=False, agent_bin=None):
    connect_url = hub_connect_url(hf_url)
    fp = fingerprint or load_fingerprint(node_name)
    agent_path = resolve_binary("agent", explicit=agent_bin, allow_download=False)
    agent_name = os.path.basename(agent_path)

    if fetch and not fp:
        common.log_info("Fetching fingerprint via SSH (port 2222 must be forwarded)...")
        fp = fetch_fingerprint_ssh()
        if fp:
            save_fingerprint(node_name, fp)

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


def run_local_start(proxy_bin=None):
    proxy = resolve_binary("proxy", explicit=proxy_bin)
    common.log_info(f"Starting local ligolo proxy on :{PROXY_PORT} ({proxy})")
    cmd = [
        proxy,
        "-laddr",
        f"https://127.0.0.1:{PROXY_PORT}",
        "-selfcert",
        "-selfcert-domain",
        "ligolo",
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[+] Local proxy stopped.")


def print_local_agent_cmd(host=None, ignore_cert=False, agent_bin=None):
    host = host or f"127.0.0.1:{PROXY_PORT}"
    if "://" not in host:
        host = f"https://{host}"
    agent = resolve_binary("agent", explicit=agent_bin)
    agent_name = os.path.basename(agent)
    print("====================================================================")
    print("                 LIGOLO LOCAL — AGENT CONNECT")
    print("====================================================================")
    flag = "-ignore-cert" if ignore_cert else "-accept-fingerprint <FP from proxy log>"
    print(f"  {agent_name} -connect {host} {flag}")
    print("====================================================================")
