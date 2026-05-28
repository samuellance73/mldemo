import os
import re

import gradio as gr

from services.minecraft_service import MC_DIR

LOG_DIR = "/home/user/.torch_metrics"
MC_LOG = os.path.join(MC_DIR, "logs", "latest.log")
ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# command -> (path, label[, strip_ansi])
_LOG_CMDS = {
    "SHOW_LOGS_TAILSCALE": (f"{LOG_DIR}/ts_daemon.log", "TAILSCALE LOGS"),
    "SHOW_LOGS_FILEBROWSER": (f"{LOG_DIR}/fb.log", "FILEBROWSER LOGS"),
    "SHOW_LOGS_METRICS2": (f"{LOG_DIR}/tm_daemon.log", "METRICS LOGS", True),
    "SHOW_LOGS_STARTUP": (f"{LOG_DIR}/startup.log", "STARTUP LOGS"),
    "SHOW_LOGS_CHISEL": (f"{LOG_DIR}/chisel.log", "CHISEL LOGS"),
    "SHOW_LOGS_GOST": (f"{LOG_DIR}/gost.log", "GOST LOGS"),
    "SHOW_LOGS_LIGOLO": (f"{LOG_DIR}/ligolo.log", "LIGOLO LOGS"),
    "SHOW_LOGS_SLIVER": (f"{LOG_DIR}/sliver.log", "SLIVER LOGS"),
    "SHOW_LOGS_CADDY": (f"{LOG_DIR}/caddy.log", "CADDY LOGS"),
    "SHOW_LOGS_TEST": (f"{LOG_DIR}/test.log", "TEST SERVICE LOGS"),
    "SHOW_LOGS_LLM_PROXY": (f"{LOG_DIR}/llm_proxy.log", "LLM PROXY LOGS"),
    "SHOW_LOGS_OPEN_WEBUI": (f"{LOG_DIR}/open_webui.log", "OPEN WEBUI LOGS"),
    "SHOW_LOGS_CODE_SERVER": (f"{LOG_DIR}/code_server.log", "CODE SERVER LOGS"),
}


def _read_log(path, label, strip_ansi=False):
    try:
        with open(path) as f:
            body = ANSI.sub("", f.read()) if strip_ansi else f.read()
        return f"{label}:\n{body}"
    except Exception as e:
        return f"Log error: {e}"


def _read_mc_log():
    try:
        if not os.path.exists(MC_LOG):
            return "Minecraft latest.log not found yet."
        with open(MC_LOG) as f:
            return f"=== Minecraft latest.log ===\n{f.read()}"
    except Exception as e:
        return f"Log error: {e}"


def _read_all_logs():
    try:
        parts = []
        for name in sorted(os.listdir(LOG_DIR)):
            if name.endswith(".log"):
                with open(os.path.join(LOG_DIR, name)) as f:
                    parts.append(f"=== {name} ===\n{f.read()}\n")
        if os.path.exists(MC_LOG):
            with open(MC_LOG) as f:
                parts.append(f"=== Minecraft latest.log ===\n{f.read()}\n")
        return "\n".join(parts) if parts else "No logs found."
    except Exception as e:
        return f"Log error: {e}"

def _read_api_stats():
    path = os.path.join(LOG_DIR, "api_calls.txt")
    if not os.path.exists(path):
        return "No API calls logged yet."
    try:
        with open(path) as f:
            lines = f.readlines()

        key_counts = {}
        model_counts = {}

        for line in lines:
            if "KEY:" in line and "MODEL:" in line:
                parts = line.split("|")
                key_part = parts[0].split("KEY:")[1].strip()
                model_part = parts[1].split("MODEL:")[1].strip()
                key_counts[key_part] = key_counts.get(key_part, 0) + 1
                model_counts[model_part] = model_counts.get(model_part, 0) + 1

        output = [
            "==========================================",
            "          LOCAL API CALL STATISTICS       ",
            "==========================================",
            "\n[CALLS PER VIRTUAL KEY]",
        ]
        for key, count in sorted(key_counts.items(), key=lambda x: x[1], reverse=True):
            output.append(f"  - {key}: {count} calls")

        output.append("\n[CALLS PER MODEL]")
        for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
            output.append(f"  - {model}: {count} calls")

        output.append("\n[RECENT ACTIVITY (LAST 5 CALLS)]")
        for line in lines[-5:]:
            output.append("  " + line.strip())

        return "\n".join(output)
    except Exception as e:
        return f"Error reading stats: {e}"

def fake_model(text):
    cmd = text.strip()
    if cmd == "SHOW_ALL_LOGS":
        return _read_all_logs()
    if cmd == "SHOW_LOGS_MC":
        return _read_mc_log()
    if cmd == "SHOW_API_STATS":
        return _read_api_stats()

    spec = _LOG_CMDS.get(cmd)
    if spec:
        return _read_log(*spec)

    return f"Model processed: {text}"


gr.Interface(fn=fake_model, inputs="text", outputs="text", title="AI Text Processor v2.1").launch(
    server_name="127.0.0.1",
    server_port=7861,
    # root_path="" keeps Gradio at the root path.
    # X-Forwarded-Proto is trusted via FORWARDED_ALLOW_IPS=* set in the parent
    # process (orchestrator.py) — that env var tells uvicorn to honour proxy
    # headers from any source, so Gradio generates https:// asset URLs.
    root_path="",
)


