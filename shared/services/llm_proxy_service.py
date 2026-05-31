import os
import subprocess
from pathlib import Path

from core.constants import (
    LITELLM_CONFIG_PATH,
    LITELLM_KEYS_PATH,
    LOCALHOST,
    METRICS_DIR,
    PORTS,
    USER_HOME,
)
from loguru import logger

from services.utils import unharden_secret

PORT = PORTS["llm_proxy"]
PREFIX = "[llm-proxy]"

# Dynamic config path: write to USER_HOME inside Docker, or local dir otherwise
CONFIG_PATH = (
    LITELLM_CONFIG_PATH if LITELLM_CONFIG_PATH.parent.exists() else "litellm.yaml"
)


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
    paths = [Path("llm_keys.yaml"), LITELLM_KEYS_PATH]
    for path in paths:
        if path.exists():
            try:
                import yaml

                with path.open() as f:
                    data = yaml.safe_load(f) or {}

                providers = data.get("providers", {})
                for provider, keys in providers.items():
                    provider_clean = provider.lower().strip()
                    if isinstance(keys, list):
                        for k in keys:
                            if isinstance(k, str) and k:
                                entries.append((provider_clean, "*", k.strip()))
                            elif isinstance(k, dict):
                                model = k.get("model")
                                specific_keys = k.get("keys", [])
                                if model and isinstance(specific_keys, list):
                                    for sk in specific_keys:
                                        if sk and isinstance(sk, str):
                                            entries.append(
                                                (
                                                    provider_clean,
                                                    model.strip(),
                                                    sk.strip(),
                                                )
                                            )
                                elif model and isinstance(k.get("keys"), str):
                                    sk = k.get("keys")
                                    if sk:
                                        entries.append(
                                            (provider_clean, model.strip(), sk.strip())
                                        )
                    elif isinstance(keys, str):
                        entries.append((provider_clean, "*", keys.strip()))
                if entries:
                    logger.info(f"{PREFIX} Loaded {len(entries)} keys from {path}")
                    return entries
            except Exception as e:
                logger.error(f"{PREFIX} Error loading keys from {path}: {e}")

    return []


def _build_config() -> str:
    """Build litellm.yaml from loaded keys and return the YAML string."""
    entries = _load_keys()
    if not entries:
        return ""

    model_entries = []
    for provider, model_name, api_key in entries:
        # Wildcard routing enables dynamic prefix matching (e.g. deepseek/*)
        if model_name == "*" or model_name == f"{provider}/*":
            model_entry = (
                f'  - model_name: "{provider}/*"\n'
                f"    litellm_params:\n"
                f"      model: {provider}/*\n"
                f'      api_key: "{api_key}"\n'
                f"    model_info:\n"
                f'      owned_by: "{provider}"\n'
            )
        else:
            # Backwards compatibility / specific named model mapping
            if model_name.startswith(f"{provider}/"):
                model_path = model_name
            else:
                model_path = f"{provider}/{model_name}"

            model_entry = (
                f'  - model_name: "{model_name}"\n'
                f"    litellm_params:\n"
                f"      model: {model_path}\n"
                f'      api_key: "{api_key}"\n'
                f"    model_info:\n"
                f'      owned_by: "{provider}"\n'
            )
        model_entries.append(model_entry)

    model_list_block = "".join(model_entries)

    master_key = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    master_key_line = f'  master_key: "{master_key}"\n' if master_key else ""

    return (
        "model_list:\n"
        f"{model_list_block}"
        "\n"
        "router_settings:\n"
        "  routing_strategy: usage-based-routing-v2\n"
        "  num_retries: 3\n"
        "  retry_after: 5\n"
        "\n"
        "litellm_settings:\n"
        "  check_provider_endpoint: true\n"
        '  success_callback: ["helicone"]\n'
        "  drop_params: true\n"  # <--- FIXED: Moved from general_settings to litellm_settings
        "\n"
        "general_settings:\n"
        f"{master_key_line}"
    )


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

    os.environ["HELICONE_API_KEY"] = "sk-helicone-vq67qfq-eonunsi-sti7roi-vjpsp6a"
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
