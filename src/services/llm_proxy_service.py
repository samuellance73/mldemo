import os
import subprocess
import urllib.request
import json
from pathlib import Path

from loguru import logger

from services.utils import deobfuscate_secret

METRICS_DIR = "/home/user/.torch_metrics"
LOG_PATH = os.path.join(METRICS_DIR, "llm_proxy.log")
CONFIG_PATH = "/home/user/litellm.yaml"
PORT = 8080
PREFIX = "[llm-proxy]"


def _fetch_models(provider: str, api_key: str):
    """Fetch available models from the provider's /v1/models endpoint."""
    urls = {
        "groq": "https://api.groq.com/openai/v1/models",
        "openai": "https://api.openai.com/v1/models",
        "openrouter": "https://openrouter.ai/api/v1/models",
        "together": "https://api.together.xyz/v1/models",
        "mistral": "https://api.mistral.ai/v1/models",
    }
    url = urls.get(provider.lower())
    if not url:
        return []
    try:
        logger.info(f"{PREFIX} Fetching models for {provider} dynamically from {url}...")
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            models = []
            for item in data.get("data", []):
                if isinstance(item, dict) and "id" in item:
                    models.append(item["id"])
            logger.info(f"{PREFIX} Discovered {len(models)} models for {provider}.")
            return models
    except Exception as e:
        logger.warning(f"{PREFIX} Failed to fetch models for {provider} dynamically: {e}")
        return []


def _build_config() -> str:
    """Build litellm.yaml from LLM_KEYS env var and return the YAML string.

    LLM_KEYS format (comma-separated, plain-text after XOR decode):
        provider:model_name:api_key, ...

    Examples:
        openai:gpt-4o:sk-abc123
        groq:*:gsk-yourkey                            # routes any model to groq/*
        groq:groq/*:gsk-yourkey                        # routes groq/xxx models to groq/xxx
        anthropic:anthropic/*:sk-ant-xyz              # routes anthropic/xxx models
    """
    raw = deobfuscate_secret(os.environ.pop("LLM_KEYS", "").strip())
    if not raw:
        return ""

    model_entries = []
    for entry in (e.strip() for e in raw.split(",") if e.strip()):
        parts = entry.split(":", 2)
        if len(parts) != 3:
            logger.warning(f"{PREFIX} Skipping malformed LLM_KEYS entry: {entry!r}")
            continue
        provider, model_name, api_key = parts

        # Dynamic model discovery for wildcard routes
        is_wildcard = (model_name == "*" or model_name == f"{provider}/*")
        if is_wildcard:
            discovered = _fetch_models(provider, api_key)
            for m in discovered:
                # Map to target model name with/without prefix matching the wildcard structure
                if model_name == "*":
                    m_name = m
                else:
                    m_name = f"{provider}/{m}"
                
                model_entries.append(
                    f"  - model_name: \"{m_name}\"\n"
                    f"    litellm_params:\n"
                    f"      model: {provider}/{m}\n"
                    f'      api_key: "{api_key}"\n'
                )

        # Append the base routing definition (serves as the wildcard fallback)
        if model_name.startswith(f"{provider}/") or model_name == "*":
            model_path = model_name if model_name != "*" else f"{provider}/*"
        else:
            model_path = f"{provider}/{model_name}"

        model_entry = (
            f"  - model_name: \"{model_name}\"\n"
            f"    litellm_params:\n"
            f"      model: {model_path}\n"
            f'      api_key: "{api_key}"\n'
        )
        model_entries.append(model_entry)

    if not model_entries:
        return ""

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
        "\n"
        "general_settings:\n"
        "  drop_params: true\n"
    )


def start():
    """Start the LiteLLM proxy server on 127.0.0.1:8080."""
    os.makedirs(METRICS_DIR, exist_ok=True)

    config_yaml = _build_config()
    if not config_yaml:
        logger.warning(f"{PREFIX} LLM_KEYS not set or empty — skipping llm_proxy")
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
