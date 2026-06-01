import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi

# Stage label → emoji + description
_STAGE_LABELS = {
    "RUNNING": ("🟢", "Running"),
    "SLEEPING": ("💤", "Sleeping"),
    "PAUSED": ("⏸ ", "Paused"),
    "BUILDING": ("🔨", "Building"),
    "APP_STARTING": ("🔄", "App starting"),
    "STOPPED": ("⛔", "Stopped"),
    "DELETING": ("🗑 ", "Deleting"),
    "ERROR": ("🔴", "Error"),
}

_HARDWARE_LABELS = {
    "cpu-basic": "CPU Basic",
    "cpu-upgrade": "CPU Upgrade",
    "t4-small": "T4 Small (GPU)",
    "t4-medium": "T4 Medium (GPU)",
    "a10g-small": "A10G Small (GPU)",
    "a10g-large": "A10G Large (GPU)",
    "a100-large": "A100 Large (GPU)",
}


def _load_nodes_config():
    _pkg = Path(__file__).resolve()
    for parent in _pkg.parents:
        candidate = parent / "manifests" / "nodes.yaml"
        if candidate.exists():
            nodes_path = candidate
            repo_root = parent
            break
    else:
        print("[-] nodes.yaml not found in any parent directory", file=sys.stderr)
        sys.exit(1)
    with nodes_path.open("r") as f:
        config = yaml.safe_load(f)
    return config.get("nodes", {}), repo_root


def _get_api(node_info, repo_root):
    _env = Path(repo_root) / ".env"
    if not _env.exists():
        _env = Path(repo_root).parent / ".env"
    load_dotenv(_env)
    token_env_key = node_info.get("token-env")
    token = (os.getenv(token_env_key) if token_env_key else None) or os.getenv(
        "HF_TOKEN"
    )
    return HfApi(token=token)


def _get_repo_id(api, node_info):
    """Return the (possibly casing-corrected) repo_id for a node."""
    repo_id = node_info.get("hf-repo")
    if not repo_id:
        return None
    try:
        identity = api.whoami()
        username = identity.get("name", "")
        if username and "/" in repo_id:
            ns, r_name = repo_id.split("/", 1)
            if ns.lower() == username.lower() and ns != username:
                repo_id = f"{username}/{r_name}"
    except Exception:
        pass
    return repo_id


def _format_runtime(runtime):
    stage = getattr(runtime, "stage", "UNKNOWN")
    hw = (
        getattr(runtime, "hardware", None)
        or getattr(runtime, "requested_hardware", None)
        or "unknown"
    )
    emoji, label = _STAGE_LABELS.get(stage, ("❓", stage))
    hw_label = _HARDWARE_LABELS.get(hw, hw)
    return f"{emoji} {label}  [{hw_label}]"


def _resolve_nodes(node_name_arg, nodes):
    """Return list of (name, info) tuples to act on."""
    if node_name_arg == "all":
        return list(nodes.items())
    if node_name_arg not in nodes:
        available = ", ".join(nodes.keys())
        print(
            f"[-] Node '{node_name_arg}' not found. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)
    return [(node_name_arg, nodes[node_name_arg])]


# ─────────────────────────────────────────────────────────
# Public actions
# ─────────────────────────────────────────────────────────


def cmd_status(node_name):
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    col = max(len(n) for n, _ in targets)

    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"  {name:<{col}}  ⚠️  No hf-repo configured")
            continue
        try:
            runtime = api.get_space_runtime(repo_id)
            status = _format_runtime(runtime)
        except Exception as e:
            status = f"🔴 Error: {e}"
        print(f"  {name:<{col}}  {status}")


def cmd_restart(node_name):
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
            continue
        try:
            api.restart_space(repo_id, factory_reboot=False)
            print(f"[+] {name}: Restart triggered → {repo_id}")
        except Exception as e:
            print(f"[-] {name}: Restart failed: {e}", file=sys.stderr)


def cmd_wake(node_name):
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
            continue
        try:
            api.resume_space(repo_id)
            print(f"[+] {name}: Waking up → {repo_id}")
        except Exception as e:
            print(f"[-] {name}: Wake failed: {e}", file=sys.stderr)


def cmd_sleep(node_name):
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
            continue
        try:
            api.pause_space(repo_id)
            print(f"[+] {name}: Paused (sleeping) → {repo_id}")
        except Exception as e:
            print(f"[-] {name}: Sleep failed: {e}", file=sys.stderr)


def cmd_vars(node_name, set_kv=None, delete_key=None):
    """List, set, or delete public Space variables (not secrets)."""
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
            continue
        try:
            if delete_key:
                api.delete_space_variable(repo_id, delete_key)
                print(f"[+] {name}: Deleted variable '{delete_key}'")
            elif set_kv:
                k, v = set_kv.split("=", 1)
                api.add_space_variable(repo_id, k.strip(), v.strip())
                print(f"[+] {name}: Set variable '{k.strip()}' = '{v.strip()}'")
            else:
                variables = api.get_space_variables(repo_id)
                if not variables:
                    print(f"  {name}: (no variables set)")
                else:
                    print(f"  {name}:")
                    for k, meta in variables.items():
                        print(f"    {k} = {meta.get('value', '')}")
        except Exception as e:
            print(f"[-] {name}: Variable operation failed: {e}", file=sys.stderr)


def cmd_secrets(node_name):
    """List the secret key names currently set on the HF Space (values are never returned by the API)."""
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    col = max(len(n) for n, _ in targets)
    for name, info in targets:
        api = _get_api(info, repo_root)
        repo_id = _get_repo_id(api, info)
        if not repo_id:
            print(f"  {name:<{col}}  ⚠️  No hf-repo configured")
            continue
        try:
            secrets = api.get_space_secrets(repo_id)
            keys = [str(s) for s in secrets] if secrets else []
            if keys:
                print(f"  {name:<{col}}  🔑 {', '.join(keys)}")
            else:
                print(f"  {name:<{col}}  (no secrets)")
        except Exception as e:
            print(f"  {name:<{col}}  🔴 Error: {e}")


def cmd_logs(node_name, follow=False, build=False):
    """Stream or snapshot container logs for a single node."""
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    if len(targets) > 1:
        print("[-] --logs only works on a single node, not 'all'", file=sys.stderr)
        sys.exit(1)

    name, info = targets[0]
    api = _get_api(info, repo_root)
    repo_id = _get_repo_id(api, info)
    if not repo_id:
        print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
        sys.exit(1)

    mode = "build" if build else "app"
    tail = "following" if follow else "snapshot"
    node_services = info.get("services") or []
    if isinstance(node_services, list):
        node_services = [str(s).lower() for s in node_services]
    print(f"[+] {name} ({repo_id}) — {mode} logs ({tail}):")
    if "test" in node_services:
        print(
            "[i] Node has 'test' enabled: look for lines starting with [TEST SERVICE] below."
        )
        print("[i] File-only detail: .torch_metrics/test.log — Gradio: SHOW_LOGS_TEST")
    print("────────────────────────────────────────────────────────────")
    saw_test = False
    try:
        for line in api.fetch_space_logs(repo_id, build=build, follow=follow):
            if "[TEST SERVICE]" in line:
                saw_test = True
            print(line, end="" if line.endswith("\n") else "\n", flush=True)
    except KeyboardInterrupt:
        print("\n[+] Log stream stopped.")
    except Exception as e:
        print(f"[-] Failed to fetch logs: {e}", file=sys.stderr)
        sys.exit(1)
    if "test" in node_services and not follow and not saw_test:
        print("────────────────────────────────────────────────────────────")
        print(
            "[!] No [TEST SERVICE] lines in this snapshot. Orchestrator may have "
            "crashed before test started, or redeploy after the test-service fix."
        )
        print("    Rebuild + deploy, then retry. In-app: SHOW_LOGS_TEST")


def cmd_dev(node_name, disable=False):
    """Enable or disable Space Dev Mode (persistent SSH shell into the container)."""
    nodes, repo_root = _load_nodes_config()
    targets = _resolve_nodes(node_name, nodes)
    if len(targets) > 1:
        print(
            "[-] --dev/--undev only works on a single node, not 'all'", file=sys.stderr
        )
        sys.exit(1)

    name, info = targets[0]
    api = _get_api(info, repo_root)
    repo_id = _get_repo_id(api, info)
    if not repo_id:
        print(f"[-] {name}: No hf-repo configured", file=sys.stderr)
        sys.exit(1)

    try:
        if disable:
            runtime = api.disable_space_dev_mode(repo_id)
            print(f"[+] {name}: Dev mode disabled. Space is restarting normally.")
            print(f"    Stage: {runtime.stage}")
        else:
            runtime = api.enable_space_dev_mode(repo_id)
            raw = runtime.raw if hasattr(runtime, "raw") else {}
            dev_info = raw.get("devMode") or raw.get("dev_mode") or {}
            ssh_url = (
                dev_info.get("sshUrl") or dev_info.get("ssh_url") or "ssh.hf.space"
            )
            ssh_port = dev_info.get("port", 22)

            print(f"[+] {name}: Dev mode ENABLED → {repo_id}")
            print(f"    Stage:  {runtime.stage}")
            print()
            print(
                "    ⚠️  Your app is NOT running. The container is in a persistent shell."
            )
            print()
            print("    Connect via SSH (requires your HF SSH key):")
            print(f"      ssh -p {ssh_port} {ssh_url}")
            print()
            print("    Your HF SSH key: https://huggingface.co/settings/keys")
            print("    To return to normal:  cc.py node <name> --undev")
    except Exception as e:
        print(f"[-] {name}: Dev mode operation failed: {e}", file=sys.stderr)
        sys.exit(1)
