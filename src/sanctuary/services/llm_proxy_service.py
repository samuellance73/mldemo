import os
import subprocess
from pathlib import Path

from sanctuary.core.constants import (
    LITELLM_BASE_CONFIG_PATH,
    LITELLM_CONFIG_PATH,
    LITELLM_KEYS_PATH,
    LOCALHOST,
    METRICS_DIR,
    PORTS,
    USER_HOME,
)
from loguru import logger

from sanctuary.common.utils import unharden_secret

PORT = PORTS["llm_proxy"]
PREFIX = "[llm-proxy]"

# Dynamic config path: write to USER_HOME inside Docker, or local dir otherwise
CONFIG_PATH = (
    LITELLM_CONFIG_PATH if LITELLM_CONFIG_PATH.parent.exists() else "litellm.yaml"
)


def _load_yaml_config() -> dict:
    """Load the raw llm_keys.yaml (or equivalent) as a dict, or return {}."""
    paths = [Path("llm_keys.yaml"), LITELLM_KEYS_PATH]
    for path in paths:
        if path.exists():
            try:
                import yaml

                with path.open() as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"{PREFIX} Error reading {path}: {e}")
    return {}


def _load_base_config() -> dict:
    """Load litellm_base.yaml (the static committed config) or return safe defaults."""
    candidates = [
        Path("main/config/litellm_base.yaml"),  # local dev (run from repo root)
        LITELLM_BASE_CONFIG_PATH,               # runtime (container / dist)
    ]
    for path in candidates:
        if path.exists():
            try:
                import yaml

                with path.open() as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"{PREFIX} Error reading base config {path}: {e}")

    logger.warning(f"{PREFIX} litellm_base.yaml not found — using built-in defaults")
    return {
        "router_settings": {"routing_strategy": "usage-based-routing-v2", "num_retries": 3, "retry_after": 5},
        "litellm_settings": {"check_provider_endpoint": True, "drop_params": True},
        "general_settings": {},
    }


def _parse_providers(providers: dict) -> list[tuple[str, str, str]]:
    """Parse the 'providers' section of llm_keys.yaml into (provider, model, key) tuples."""
    entries = []
    for provider, keys in providers.items():
        provider_clean = provider.lower().strip()
        if isinstance(keys, str):
            entries.append((provider_clean, "*", keys.strip()))
        elif isinstance(keys, list):
            for k in keys:
                if isinstance(k, str) and k:
                    entries.append((provider_clean, "*", k.strip()))
                elif isinstance(k, dict):
                    model = k.get("model")
                    specific_keys = k.get("keys", [])
                    if model and isinstance(specific_keys, list):
                        for sk in specific_keys:
                            if sk and isinstance(sk, str):
                                entries.append((provider_clean, model.strip(), sk.strip()))
                    elif model and isinstance(specific_keys, str) and specific_keys:
                        entries.append((provider_clean, model.strip(), specific_keys.strip()))
    return entries

def _load_keys() -> list[tuple[str, str, str]]:
    """Load keys from the encrypted LLM_KEYS environment variable, or fallback to llm_keys.yaml.

    Returns:
        List of tuples: (provider, model_name, api_key)
    """
    entries = []

    # 1. Primary path: Load from the XOR-obfuscated LLM_KEYS environment variable (standard Space deployment)
    llm_keys_env = os.environ.get("LLM_KEYS", "").strip()
    if llm_keys_env:
        try:
            decoded = unharden_secret(llm_keys_env)
            if decoded:
                for chunk in decoded.split(","):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    parts = chunk.split(":", 2)
                    if len(parts) == 3:
                        provider = parts[0].strip()
                        model_name = parts[1].strip()
                        api_key = parts[2].strip()
                        entries.append((provider, model_name, api_key))
                if entries:
                    logger.info(
                        f"{PREFIX} Loaded {len(entries)} keys from LLM_KEYS environment variable."
                    )
                    return entries
        except Exception as e:
            logger.error(f"{PREFIX} Failed to parse LLM_KEYS environment variable: {e}")

    # 2. Fallback path: Load from physical yaml file (local development environment)
    data = _load_yaml_config()
    if data:
        entries = _parse_providers(data.get("providers", {}))
        if entries:
            logger.info(f"{PREFIX} Loaded {len(entries)} keys from llm_keys.yaml")
            return entries



    return []


def _build_config() -> str:
    """Build litellm.yaml by injecting the dynamic model_list into litellm_base.yaml."""
    import yaml

    entries = _load_keys()
    if not entries:
        return ""

    model_list = []
    for provider, model_name, api_key in entries:
        if model_name == "*" or model_name == f"{provider}/*":
            model_list.append({
                "model_name": f"{provider}/*",
                "litellm_params": {"model": f"{provider}/*", "api_key": api_key},
                "model_info": {"owned_by": provider},
            })
        else:
            model_path = model_name if model_name.startswith(f"{provider}/") else f"{provider}/{model_name}"
            model_list.append({
                "model_name": model_name,
                "litellm_params": {"model": model_path, "api_key": api_key},
                "model_info": {"owned_by": provider},
            })

    config = _load_base_config()
    config["model_list"] = model_list

    master_key = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if master_key:
        config.setdefault("general_settings", {})["master_key"] = master_key

    return yaml.dump(config, default_flow_style=False, allow_unicode=True)


def start(log):
    """Start the LiteLLM proxy server on {LOCALHOST}:{PORT}."""
    Path(METRICS_DIR).mkdir(parents=True, exist_ok=True)

    config_yaml = _build_config()
    if not config_yaml:
        logger.warning(
            f"{PREFIX} No API keys loaded from environment or llm_keys.yaml — skipping llm_proxy"
        )
        return

    Path(CONFIG_PATH).write_text(config_yaml)
    logger.info(f"{PREFIX} Config written to {CONFIG_PATH}")
    os.environ["DISABLE_ADMIN_UI"] = "True"

    litellm_bin = (
        "/opt/venv-litellm/bin/litellm"
        if Path("/opt/venv-litellm/bin/litellm").exists()
        else "litellm"
    )
    cmd = [
        litellm_bin,
        "--config",
        CONFIG_PATH,
        "--port",
        str(PORT),
        "--host",
        LOCALHOST,
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(USER_HOME) + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    # Global environment fallback to force parameter dropping across all sessions
    env["LITELLM_DROP_PARAMS"] = "True"

    # Register the custom logger in-process via the environment so LiteLLM's
    # proxy server picks it up through its standard import mechanism without
    # going through FastAPI lifespan machinery (avoids merged_lifespan recursion).
    env["LITELLM_CUSTOM_CALLBACK_MODULE"] = "services.custom_callbacks"
    env["LITELLM_CUSTOM_CALLBACK_HANDLER"] = "proxy_handler_instance"

    proc = subprocess.Popen(cmd, stdout=log, stderr=log, env=env)

    logger.success(
        f"{PREFIX} litellm proxy started on {LOCALHOST}:{PORT} (pid {proc.pid})"
    )
