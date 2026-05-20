import subprocess
import sys
import time
import socket as _socket
import cc_utils.common as common

def run_gost_client(hf_url, auth, proxy_mode, run_ssh_fn):
    # 1. Normalize the HF URL (remove existing schemes)
    clean_url = hf_url.replace("https://", "").replace("http://", "").rstrip('/')

    # 2. Construct the client connection string
    # Must use relay+mwss for TLS traversal, append :443, and force the path query parameter
    ws_url = f"relay+mwss://{auth}@{clean_url}:443/gost-bridge?path=/gost-bridge"

    if proxy_mode == "socks5":
        listen_flag = "socks5://:1080"
        print(f"[+] Creating local SOCKS5 proxy on port 1080")
    else:
        listen_flag = "tcp://:2222/127.0.0.1:2222"
        print(f"[+] Forwarding local port 2222 to container SSH (2222)")

    cmd = [
        "gost",
        "-L", listen_flag,
        "-F", ws_url
    ]

    print(f"[+] Launching GOST client -> {ws_url}")
    
    if proxy_mode == "ssh":
        try:
            stdout_dest = None if common.DEBUG_MODE else subprocess.DEVNULL
            stderr_dest = None if common.DEBUG_MODE else subprocess.DEVNULL
            proc = subprocess.Popen(cmd, stdout=stdout_dest, stderr=stderr_dest)
            # Wait for GOST to bind the local port (up to 10s)
            print("[+] Waiting for GOST to bind local port 2222...", end="", flush=True)
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    with _socket.create_connection(("127.0.0.1", 2222), timeout=0.5):
                        pass
                    print(" ready.")
                    break
                except OSError:
                    print(".", end="", flush=True)
                    time.sleep(0.5)
            else:
                print("\n[-] Timed out waiting for GOST to bind port 2222.")
                proc.terminate()
                sys.exit(1)
            
            run_ssh_fn(2222)
            print("[+] Terminating GOST client.")
            proc.terminate()
            proc.wait()
        except FileNotFoundError:
            print("[-] Error: 'gost' binary not found. Please install from https://github.com/go-gost/gost", file=sys.stderr)
            sys.exit(1)
    else:
        print("Press Ctrl+C to stop the tunnel and exit.")
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n[+] Closing GOST tunnel.")
        except FileNotFoundError:
            print("[-] Error: 'gost' binary not found. Please install from https://github.com/go-gost/gost", file=sys.stderr)
            sys.exit(1)
