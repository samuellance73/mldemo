import os
import subprocess
import threading
import time
from pathlib import Path

from loguru import logger

METRICS_DIR = "/home/user/.torch_metrics"
PORT = 3000
PREFIX = "[open-webui]"
VENV_DIR = "/home/user/.venv-openwebui"
OWUI_BIN = f"{VENV_DIR}/bin/open-webui"


def _ensure_installed(log=None) -> str:
    """Ensure open-webui is installed and return its binary path.

    In normal operation open-webui is pre-installed into ``VENV_DIR`` during
    the Docker build, so this function returns immediately after finding the
    binary.  The ``uv venv`` + ``uv pip install`` fallback path only runs when
    the binary is absent (e.g. local/dev runs outside the baked image).

    Returns the path to the open-webui binary.
    """
    if Path(OWUI_BIN).exists():
        logger.debug(
            f"{PREFIX} open-webui binary found at {OWUI_BIN}, skipping install."
        )
        return OWUI_BIN

    logger.info(
        f"{PREFIX} open-webui not found — running first-boot install into {VENV_DIR} ..."
    )
    logger.info(f"{PREFIX} This will take a few minutes on the first start only.")

    def _run(cmd, **kwargs):
        """Run a command, streaming output to log handle if provided."""
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
    _run(["uv", "venv", VENV_DIR])
    _run(["uv", "pip", "install", "--python", VENV_DIR, "--no-cache-dir", "open-webui"])
    elapsed = time.time() - t0
    logger.success(
        f"{PREFIX} open-webui installed in {elapsed:.1f}s — subsequent boots will be instant."
    )
    return OWUI_BIN


def _start_worker(log, env):
    """Background worker: install if needed, then launch Open WebUI."""
    open_webui_bin = _ensure_installed(log)
    cmd = [
        open_webui_bin,
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
    ]

    logger.info(f"{PREFIX} Starting Open WebUI on 127.0.0.1:{PORT}...")
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=log,
        env=env,
    )

    logger.success(
        f"{PREFIX} Open WebUI started (pid {proc.pid}). "
        f"Reachable at http://127.0.0.1:{PORT} "
        f"exclusively over Tailscale / private overlay networks."
    )


def start(log):
    """Launch Open WebUI bound exclusively to 127.0.0.1:3000.

    ``log`` is the TeeLogger (or plain file) handle provided by setup_service_logs();
    subprocess stdout/stderr are piped through it so Open WebUI output appears in
    the main container log stream as well as open_webui.log on disk.

    Binding to localhost means the process is completely invisible on the
    public internet. Access is secured and routed exclusively through the
    Tailscale secure tunnel overlay or other private network paths.

    The actual install + launch runs in a daemon thread so the orchestrator
    is never blocked — even on a first-boot pip install that takes minutes.
    """
    Path(METRICS_DIR).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # Point Open WebUI at the local LiteLLM proxy (same node).
    env["OPENAI_API_BASE_URL"] = "http://127.0.0.1:8080/v1"
    env["OPENAI_API_KEY"] = env.get("LITELLM_MASTER_KEY", "none") or "none"
    # Disable the default login wall — access is controlled by nginx path routing
    # and/or Tailscale network isolation. Enable if you want a login screen.
    env["WEBUI_AUTH"] = "False"
    # Stable secret keys so the container never regenerates them on restart.
    env.setdefault("WEBUI_SECRET_KEY", "sanctuary_owui_secret_key_server01")
    env.setdefault(
        "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY",
        "sanctuary_owui_oauth_token_key_server01_32bytes",
    )
    # Data directory inside the metrics/state folder so it survives redeploys.
    env["DATA_DIR"] = str(Path(METRICS_DIR) / "open_webui_data")
    Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    # CRITICAL: HF Spaces injects PORT=7860 into the environment. Open WebUI
    # reads PORT (and UVICORN_PORT) and will bind to 7860, stealing the public
    # port from Caddy before it starts. Override both to lock it to localhost:3000.
    env["PORT"] = str(PORT)
    env["HOST"] = "127.0.0.1"
    env["UVICORN_HOST"] = "127.0.0.1"
    env["UVICORN_PORT"] = str(PORT)

    # --- Performance Profile: Offloaded Embeddings (RAG) ---
    # Instead of loading all-MiniLM-L6-v2 (~500MB) directly into Open WebUI's
    # memory, delegate all embedding calls to the local LiteLLM proxy on :8080.
    # Open WebUI becomes a thin HTTP client; zero ML weights are loaded in-process.
    env["ENABLE_RAG"] = "True"
    env["RAG_EMBEDDING_ENGINE"] = "openai"
    env["RAG_EMBEDDING_OPENAI_API_BASE_URL"] = "http://127.0.0.1:8080/v1"
    env["RAG_EMBEDDING_OPENAI_API_KEY"] = (
        env.get("LITELLM_MASTER_KEY", "none") or "none"
    )

    # --- Performance Profile: Browser-side STT (Zero Server Cost) ---
    # Whisper models require >500MB RAM and heavy CPU to run server-side.
    # Setting AUDIO_STT_ENGINE=webapi delegates speech-to-text entirely to the
    # user's browser (Web Speech API) — consuming 0 bytes of HF node RAM.
    # TTS is cleared so Open WebUI does not attempt a local TTS engine either.
    env["AUDIO_STT_ENGINE"] = "webapi"
    env["AUDIO_TTS_ENGINE"] = ""

    t = threading.Thread(target=_start_worker, args=(log, env), daemon=True)
    t.start()
    logger.info(
        f"{PREFIX} install/launch dispatched to background thread (orchestrator unblocked)."
    )
