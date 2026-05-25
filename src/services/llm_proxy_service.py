import os
import subprocess
from pathlib import Path

from loguru import logger

from services.utils import deobfuscate_secret

METRICS_DIR = "/home/user/.torch_metrics"
LOG_PATH = os.path.join(METRICS_DIR, "llm_proxy.log")
CONFIG_PATH = "/home/user/litellm.yaml"
PORT = 8080
PREFIX = "[llm-proxy]"


def _build_config() -> str:
    """Build litellm.yaml from LLM_KEYS env var and return the YAML string.

    LLM_KEYS format (comma-separated, plain-text after XOR decode):
        provider:model_name:api_key, ...

    Examples:
        openai:gpt-4o:sk-abc123
        anthropic:claude-3-5-sonnet-20241022:sk-ant-xyz
        gemini:gemini-2.0-flash:AIza...
        openrouter:openai/gpt-4o:sk-or-...
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
        model_entries.append(
            f"  - model_name: {model_name}\n"
            f"    litellm_params:\n"
            f"      model: {provider}/{model_name}\n"
            f'      api_key: "{api_key}"\n'
        )

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
