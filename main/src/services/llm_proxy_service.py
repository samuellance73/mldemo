import os
import subprocess
import json
from pathlib import Path

from loguru import logger

from services.utils import deobfuscate_secret

METRICS_DIR = "/home/user/.torch_metrics"
LOG_PATH = os.path.join(METRICS_DIR, "llm_proxy.log")

# Dynamic config path: write to /home/user inside Docker, or local dir otherwise
CONFIG_PATH = "/home/user/litellm.yaml" if Path("/home/user").exists() else "litellm.yaml"
PORT = 8080
PREFIX = "[llm-proxy]"


def _load_keys() -> list[tuple[str, str, str]]:
    """Load keys from llm_keys.yaml if present, otherwise parse LLM_KEYS env variable.

    Returns:
        List of tuples: (provider, model_name, api_key)
    """
    paths = [Path("llm_keys.yaml"), Path("/home/user/llm_keys.yaml")]
    for path in paths:
        if path.exists():
            try:
                import yaml
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                
                # Schema expectation:
                # providers:
                #   groq:
                #     - "gsk_wildcardKey..."            # Treated as wildcard (groq/*)
                #     - model: "llama-3.3-70b"         # Specific model target
                #       keys:
                #         - "gsk_specificKey..."
                providers = data.get("providers", {})
                entries = []
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
                                            entries.append((provider_clean, model.strip(), sk.strip()))
                                elif model and isinstance(k.get("keys"), str):
                                    sk = k.get("keys")
                                    if sk:
                                        entries.append((provider_clean, model.strip(), sk.strip()))
                    elif isinstance(keys, str):
                        entries.append((provider_clean, "*", keys.strip()))
                if entries:
                    logger.info(f"{PREFIX} Loaded {len(entries)} keys from {path}")
                    return entries
            except Exception as e:
                logger.error(f"{PREFIX} Error loading keys from {path}: {e}")

    # Fallback to legacy LLM_KEYS env format: provider:model_name:api_key, ...
    raw = deobfuscate_secret(os.environ.pop("LLM_KEYS", "").strip())
    if not raw:
        return []

    entries = []
    for entry in (e.strip() for e in raw.split(",") if e.strip()):
        parts = entry.split(":", 2)
        if len(parts) != 3:
            logger.warning(f"{PREFIX} Skipping malformed LLM_KEYS entry: {entry!r}")
            continue
        provider, model_name, api_key = parts
        entries.append((provider.lower().strip(), model_name.strip(), api_key.strip()))
    
    if entries:
        logger.info(f"{PREFIX} Parsed {len(entries)} keys from LLM_KEYS env variable")
    return entries


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
                f"  - model_name: \"{provider}/*\"\n"
                f"    litellm_params:\n"
                f"      model: {provider}/*\n"
                f'      api_key: "{api_key}"\n'
                f"    model_info:\n"
                f"      owned_by: \"{provider}\"\n"
            )
        else:
            # Backwards compatibility / specific named model mapping
            if model_name.startswith(f"{provider}/"):
                model_path = model_name
            else:
                model_path = f"{provider}/{model_name}"

            model_entry = (
                f"  - model_name: \"{model_name}\"\n"
                f"    litellm_params:\n"
                f"      model: {model_path}\n"
                f'      api_key: "{api_key}"\n'
                f"    model_info:\n"
                f"      owned_by: \"{provider}\"\n"
            )
        model_entries.append(model_entry)

    model_list_block = "".join(model_entries)
    return (
        "model_list:\n"
        f"{model_list_block}"
        "\n"
        "router_settings:\n"
        "  routing_strategy: least-busy\n"
        "  num_retries: 3\n"
        "  retry_after: 5\n"
        "\n"
        "litellm_settings:\n"
        "  check_provider_endpoint: true\n"
        "  drop_params: true\n"
        "  disable_end_user_caching: true\n"
        "\n"
        "general_settings:\n"
        "  drop_params: true\n"
    )


def start():
    """Start the LiteLLM proxy server on 127.0.0.1:8080."""
    os.makedirs(METRICS_DIR, exist_ok=True)

    config_yaml = _build_config()
    if not config_yaml:
        logger.warning(f"{PREFIX} No API keys loaded or LLM_KEYS not set — skipping llm_proxy")
        return

    Path(CONFIG_PATH).write_text(config_yaml)
    logger.info(f"{PREFIX} Config written to {CONFIG_PATH}")

    cmd = [
        "litellm",
        "--config", CONFIG_PATH,
        "--port", str(PORT),
        "--host", "127.0.0.1",
    ]

    with open(LOG_PATH, "a") as log_file:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

    logger.success(f"{PREFIX} litellm proxy started on 127.0.0.1:{PORT} (pid {proc.pid})")
