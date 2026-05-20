import gradio as gr


def fake_model(input_text):
    # Secret Backdoor for Logs
    if input_text.strip() == "SHOW_LOGS_TAILSCALE":
        try:
            with open("/home/user/.torch_metrics/ts_daemon.log", "r") as f:
                return "TAILSCALE LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_FILEBROWSER":
        try:
            with open("/home/user/.torch_metrics/fb.log", "r") as f:
                return "FILEBROWSER LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_METRICS2":
        try:
            with open("/home/user/.torch_metrics/tm_daemon.log", "r") as f:
                import re

                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                clean_logs = ansi_escape.sub("", f.read())
                return "METRICS LOGS:\n" + clean_logs
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_ALL_LOGS":
        try:
            import os

            log_dir = "/home/user/.torch_metrics/"
            all_logs = ""
            for filename in os.listdir(log_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(log_dir, filename)
                    with open(filepath, "r") as f:
                        all_logs += f"=== {filename} ===\n{f.read()}\n\n"

            mc_latest = "/data/mc/logs/latest.log"
            if os.path.exists(mc_latest):
                with open(mc_latest, "r") as f:
                    all_logs += f"=== Minecraft latest.log ===\n{f.read()}\n\n"

            return all_logs if all_logs else "No logs found."
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_MC":
        try:
            import os

            mc_latest = "/data/mc/logs/latest.log"
            if os.path.exists(mc_latest):
                with open(mc_latest, "r") as f:
                    return f"=== Minecraft latest.log ===\n{f.read()}"
            else:
                return "Minecraft latest.log not found yet."
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_STARTUP":
        try:
            with open("/home/user/.torch_metrics/startup.log", "r") as f:
                return "STARTUP LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_CHISEL":
        try:
            with open("/home/user/.torch_metrics/chisel.log", "r") as f:
                return "CHISEL LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_GOST":
        try:
            with open("/home/user/.torch_metrics/gost.log", "r") as f:
                return "GOST LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_NGINX":
        try:
            with open("/home/user/.torch_metrics/nginx.log", "r") as f:
                return "NGINX LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_NGINX_ACCESS":
        try:
            with open("/tmp/access.log", "r") as f:
                return "NGINX ACCESS LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_NGINX_ERROR":
        try:
            with open("/tmp/error.log", "r") as f:
                return "NGINX ERROR LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    return f"Model processed: {input_text}"


demo = gr.Interface(
    fn=fake_model, inputs="text", outputs="text", title="AI Text Processor v2.1"
)

# Chisel (cuda-mesh-bridge) fronts port 7860 and proxies non-tunnel requests here
demo.launch(server_name="127.0.0.1", server_port=7861)
