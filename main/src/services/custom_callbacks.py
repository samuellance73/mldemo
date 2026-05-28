from datetime import datetime
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

METRICS_DIR = "/home/user/.torch_metrics"
API_CALLS_LOG = Path(METRICS_DIR) / "api_calls.txt"


class SimpleTextLogger(CustomLogger):
    def _write(self, kwargs):
        try:
            user_key = kwargs.get("user_api_key_alias") or "unknown-key"
            model = kwargs.get("model") or "unknown-model"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] KEY: {user_key} | MODEL: {model}\n"
            Path(METRICS_DIR).mkdir(parents=True, exist_ok=True)
            with API_CALLS_LOG.open("a") as f:
                f.write(log_line)
        except Exception:
            pass

    # Sync path (direct SDK usage)
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs)

    # Async path (LiteLLM proxy server — this is the one that actually fires)
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._write(kwargs)


# LiteLLM resolves this instance by module path
proxy_handler_instance = SimpleTextLogger()
