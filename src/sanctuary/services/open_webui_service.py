import os
import subprocess
import threading
import time
from pathlib import Path

from sanctuary.core.constants import LOCALHOST, METRICS_DIR, PORTS, VENV_OPENWEBUI_DIR
from loguru import logger

PORT = PORTS["open_webui"]
PREFIX = "[open-webui]"
OWUI_BIN = f"{VENV_OPENWEBUI_DIR}/bin/open-webui"


def _ensure_installed(log=None) -> str:
    if Path(OWUI_BIN).exists():
        logger.debug(
            f"{PREFIX} open-webui binary found at {OWUI_BIN}, skipping install."
        )
        return OWUI_BIN

    logger.info(
        f"{PREFIX} open-webui not found — running first-boot install into {VENV_OPENWEBUI_DIR} ..."
    )
    logger.info(f"{PREFIX} This will take a few minutes on the first start only.")

    def _run(cmd, **kwargs):
        proc = subprocess.Popen(
            cmd,
            stdout=log if log else subprocess.PIPE,
            stderr=log if log else subprocess.STDOUT,
            **kwargs,
        )
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"{PREFIX} Install step failed: {' '.join(cmd)} (exit {proc.returncode})"
            )

    t0 = time.time()
    _run(["uv", "venv", str(VENV_OPENWEBUI_DIR)])
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(VENV_OPENWEBUI_DIR),
            "--no-cache-dir",
            "open-webui",
        ]
    )
    elapsed = time.time() - t0
    logger.success(
        f"{PREFIX} open-webui installed in {elapsed:.1f}s — subsequent boots will be instant."
    )
    return OWUI_BIN


def _start_worker(log, env):
    open_webui_bin = _ensure_installed(log)
    cmd = [
        open_webui_bin,
        "serve",
        "--host",
        LOCALHOST,
        "--port",
        str(PORT),
    ]

    logger.info(f"{PREFIX} Starting Open WebUI on {LOCALHOST}:{PORT}...")
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=log,
        env=env,
    )

    logger.success(
        f"{PREFIX} Open WebUI started (pid {proc.pid}). "
        f"Reachable at http://{LOCALHOST}:{PORT} "
        f"exclusively over Tailscale / private overlay networks."
    )


def start(log):
    Path(METRICS_DIR).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["OPENAI_API_BASE_URL"] = f"http://{LOCALHOST}:{PORTS['llm_proxy']}/v1"
    env["OPENAI_API_KEY"] = env.get("LITELLM_MASTER_KEY", "none") or "none"
    env["WEBUI_AUTH"] = "False"
    env.setdefault("WEBUI_SECRET_KEY", "sanctuary_owui_secret_key_server01")
    env.setdefault(
        "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY",
        "sanctuary_owui_oauth_token_key_server01_32bytes",
    )
    env["DATA_DIR"] = str(Path(METRICS_DIR) / "open_webui_data")
    Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    env["PORT"] = str(PORT)
    env["HOST"] = LOCALHOST
    env["UVICORN_HOST"] = LOCALHOST
    env["UVICORN_PORT"] = str(PORT)

    env["ENABLE_RAG"] = "True"
    env["RAG_EMBEDDING_ENGINE"] = "openai"
    env["RAG_EMBEDDING_OPENAI_API_BASE_URL"] = (
        f"http://{LOCALHOST}:{PORTS['llm_proxy']}/v1"
    )
    env["RAG_EMBEDDING_OPENAI_API_KEY"] = (
        env.get("LITELLM_MASTER_KEY", "none") or "none"
    )

    env["AUDIO_STT_ENGINE"] = "webapi"
    env["AUDIO_TTS_ENGINE"] = ""

    t = threading.Thread(target=_start_worker, args=(log, env), daemon=True)
    t.start()
    logger.info(
        f"{PREFIX} install/launch dispatched to background thread (orchestrator unblocked)."
    )
