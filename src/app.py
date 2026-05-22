import os
import re

import gradio as gr

LOG_DIR = "/home/user/.torch_metrics"
MC_LOG = "/data/mc/logs/latest.log"
ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# command -> (path, label[, strip_ansi])
_LOG_CMDS = {
    "SHOW_LOGS_TAILSCALE": (f"{LOG_DIR}/ts_daemon.log", "TAILSCALE LOGS"),
    "SHOW_LOGS_FILEBROWSER": (f"{LOG_DIR}/fb.log", "FILEBROWSER LOGS"),
    "SHOW_LOGS_METRICS2": (f"{LOG_DIR}/tm_daemon.log", "METRICS LOGS", True),
    "SHOW_LOGS_STARTUP": (f"{LOG_DIR}/startup.log", "STARTUP LOGS"),
    "SHOW_LOGS_CHISEL": (f"{LOG_DIR}/chisel.log", "CHISEL LOGS"),
    "SHOW_LOGS_GOST": (f"{LOG_DIR}/gost.log", "GOST LOGS"),
    "SHOW_LOGS_SLIVER": (f"{LOG_DIR}/sliver.log", "SLIVER LOGS"),
    "SHOW_LOGS_NGINX": (f"{LOG_DIR}/nginx.log", "NGINX LOGS"),
    "SHOW_LOGS_NGINX_ACCESS": ("/tmp/access.log", "NGINX ACCESS LOGS"),
    "SHOW_LOGS_NGINX_ERROR": ("/tmp/error.log", "NGINX ERROR LOGS"),
    "SHOW_LOGS_TEST": (f"{LOG_DIR}/test.log", "TEST SERVICE LOGS"),
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


def fake_model(text):
    cmd = text.strip()
    if cmd == "SHOW_ALL_LOGS":
        return _read_all_logs()
    if cmd == "SHOW_LOGS_MC":
        return _read_mc_log()

    spec = _LOG_CMDS.get(cmd)
    if spec:
        return _read_log(*spec)

    return f"Model processed: {text}"


gr.Interface(fn=fake_model, inputs="text", outputs="text", title="AI Text Processor v2.1").launch(
    server_name="127.0.0.1", server_port=7861
)
