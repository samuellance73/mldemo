import json
import os
import random
import socket
import string
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger
from sanctuary.common.utils import unharden_secret

from sanctuary.core.constants import LOCALHOST, PORTS, ENABLED_SERVICES_PATH
from sanctuary.core.service_logs import setup_service_logs

logger.info("--- BOOTING AI MODEL SERVER ---")


def load_enabled_services():
    """Load per-node service list written at deploy time, allowing env overrides."""
    env_services = os.environ.get("SERVICES")
    if env_services:
        logger.info("Using services configuration from environment: {}", env_services)
        return frozenset(s.strip().lower() for s in env_services.split(",") if s.strip()), {}

    try:
        with open(ENABLED_SERVICES_PATH, "r") as f:
            data = json.load(f)
        services = data.get("services") or []
        # Unify all storage configurations into the single config block written by deploy.py
        storage_config = data.get("storage", {})
        return frozenset(s.strip().lower() for s in services if s), storage_config
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return frozenset(), {}


def wait_for_port(host, port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    enabled, storage_config = load_enabled_services()
    if enabled:
        logger.info("Enabled services: {}", ", ".join(sorted(enabled)))
    else:
        logger.info("Minimal core only (no optional services enabled)")

    # 1. Pop standard VPN and SSH secrets from system environment space
    _ts_raw = os.environ.pop("A", None) or os.environ.pop("TAILSCALE", "")
    _playit_raw = os.environ.pop("P", None) or os.environ.pop("PLAYIT", "")
    _ssh_raw = os.environ.pop("PASS", None) or os.environ.pop("SSH", "")
    _cf_raw = os.environ.pop("CF", None) or os.environ.pop("CLOUDFLARE", "")
    
    ts_token = unharden_secret(_ts_raw.strip()) if _ts_raw else ""
    playit_tok = unharden_secret(_playit_raw.strip()) if _playit_raw else ""
    ssh_pwd_cfg = unharden_secret(_ssh_raw.strip()) if _ssh_raw else ""
    cf_tok = unharden_secret(_cf_raw.strip()) if _cf_raw else ""
    del _ts_raw, _playit_raw, _ssh_raw, _cf_raw

    # 2. Resolve storage/backup credentials ONCE to prevent double-popping conflicts
    storage_provider = storage_config.get("provider")
    
    hf_token = ""
    s3_access_key = ""
    s3_secret_key = ""

    if storage_provider == "huggingface":
        hf_token_env = storage_config.get("token-env")
        if hf_token_env:
            # Pop the token-env key (e.g. "HF2") safely
            _hf_token_raw = os.environ.pop(hf_token_env, None)
            hf_token = unharden_secret(_hf_token_raw.strip()) if _hf_token_raw else ""
            del _hf_token_raw
            # Set in-memory HF_TOKEN so standard internal python libraries can find it
            os.environ["HF_TOKEN"] = hf_token
            
    elif storage_provider == "s3":
        s3_access_key_env = storage_config.get("access-key-env")
        s3_secret_key_env = storage_config.get("secret-key-env")
        
        if s3_access_key_env:
            _s3_access_key_raw = os.environ.pop(s3_access_key_env, None)
            s3_access_key = unharden_secret(_s3_access_key_raw.strip()) if _s3_access_key_raw else ""
            del _s3_access_key_raw
            
        if s3_secret_key_env:
            _s3_secret_key_raw = os.environ.pop(s3_secret_key_env, None)
            s3_secret_key = unharden_secret(_s3_secret_key_raw.strip()) if _s3_secret_key_raw else ""
            del _s3_secret_key_raw

    # 3. Spawn background services
    if "test" in enabled:
        from sanctuary.services import test_service
        test_service.start()

    logs = setup_service_logs()

    if "caddy" in enabled:
        from sanctuary.services import caddy_service
        caddy_service.start(logs.caddy)

    if "portal" in enabled:
        from sanctuary.services import portal_service
        portal_proc = portal_service.start(logs.portal)

    if "tailscale" in enabled:
        from sanctuary.services import tailscale_service
        tailscale_service.start_daemon(logs.ts)

    time.sleep(2)
    logger.info("Warming up text-generation pipelines...")

    if "filebrowser" in enabled:
        from sanctuary.services import filebrowser_service
        filebrowser_service.start(logs.fb, pwd=ssh_pwd_cfg)

    if "playit" in enabled:
        from sanctuary.services import playit_service
        playit_service.start(logs.tm, token=playit_tok)

    if "chisel" in enabled:
        from sanctuary.services import chisel_service
        chisel_service.start(logs.chisel)

    if "cloudflare" in enabled:
        from sanctuary.services import cloudflare_service
        cloudflare_service.start(logs.cloudflare, token=cf_tok)
        cf_tok = ""

    if "gost" in enabled:
        from sanctuary.services import gost_service
        gost_service.start(logs.gost, pwd=ssh_pwd_cfg)

    if "ligolo" in enabled:
        from sanctuary.services import ligolo_service
        ligolo_service.start(logs.ligolo)

    if "sliver" in enabled:
        from sanctuary.services import sliver_service
        sliver_service.start(logs.sliver)

    if "tailscale" in enabled:
        time.sleep(5)
        tailscale_service.connect(logs.ts, ts_token)
        ts_token = ""

    username = Path.home().name
    if ssh_pwd_cfg:
        ssh_pwd = ssh_pwd_cfg
        logger.info("Setting SSH password from Hugging Face Secrets (PASS)...")
    else:
        ssh_pwd = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        logger.success(f"Generated SSH Password for '{username}': {ssh_pwd}")
    ssh_pwd_cfg = ""

    try:
        subprocess.run(
            ["sudo", "/usr/sbin/chpasswd"],
            input=f"{username}:{ssh_pwd}\n",
            text=True,
            check=True,
        )
    except Exception as e:
        logger.error(f"Failed to set password: {e}")
    ssh_pwd = ""

    subprocess.Popen(
        "sudo /usr/sbin/sshd -D", shell=True, stdout=logs.ts, stderr=logs.ts
    )

    if "playit" in enabled:
        if not wait_for_port(LOCALHOST, PORTS["ssh"], timeout=30):
            logger.error(f"SSH daemon did not become ready on port {PORTS['ssh']}")
        else:
            logger.info(f"SSH daemon ready on port {PORTS['ssh']}")
            playit_service.start_xor_bridge()

    if "minecraft" in enabled:
        from sanctuary.services import minecraft_service
        minecraft_service.start()

    if "llm_proxy" in enabled:
        from sanctuary.services import llm_proxy_service
        llm_proxy_service.start(logs.llm_proxy)

    if "open_webui" in enabled:
        from sanctuary.services import open_webui_service
        open_webui_service.start(logs.open_webui)

    if "code_server" in enabled:
        from sanctuary.services import code_server_service
        code_server_service.start(logs.code_server)

    if "visual_debugger" in enabled:
        from sanctuary.services import visual_debugger_service
        visual_debugger_service.start(logs.visual_debugger)

    # 4. Storage Sync (Library Tool)
    if "storage_sync" in enabled:
        from sanctuary.services import storage_sync_service
        if storage_provider == "huggingface":
            hf_repo_id = storage_config.get("repo-id")
            storage_sync_service.start(
                logs.storage_sync, sync_type="huggingface", repo_id=hf_repo_id, token=hf_token
            )
        elif storage_provider == "s3":
            s3_bucket_name = storage_config.get("bucket-name")
            s3_endpoint = storage_config.get("endpoint")
            storage_sync_service.start(
                logs.storage_sync, 
                sync_type="s3", 
                bucket_name=s3_bucket_name, 
                endpoint=s3_endpoint, 
                access_key=s3_access_key, 
                secret_key=s3_secret_key
            )

    # 5. State Sync (Continuous Background Daemon)
    if "state_sync" in enabled:
        from sanctuary.services import state_sync_service
        if storage_provider == "huggingface":
            hf_repo_id = storage_config.get("repo-id")
            state_sync_service.start(
                storage_log=logs.state_sync,
                sync_type="huggingface",
                repo_id=hf_repo_id,
                token=hf_token
            )
        elif storage_provider == "s3":
            s3_bucket_name = storage_config.get("bucket-name")
            s3_endpoint = storage_config.get("endpoint")
            state_sync_service.start(
                storage_log=logs.state_sync,
                sync_type="s3",
                bucket_name=s3_bucket_name,
                endpoint=s3_endpoint,
                access_key=s3_access_key,
                secret_key=s3_secret_key
            )

    logger.success("Model loaded successfully. Background services active.")
    logger.info("Background services are active.")

    if "portal" in enabled and "portal_proc" in locals():
        portal_proc.wait()
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down orchestrator...")


if __name__ == "__main__":
    main()