import subprocess
import sys
import time
import socket as _socket
import urllib.parse
import os
import random
import cc_utils.common as common

def run_gost_client(hf_url, auth, ssh_enabled, proxy_enabled, local_forward, run_ssh_fn, transport="mwss"):
    # 1. Normalize the HF URL (remove existing schemes)
    clean_url = hf_url.replace("https://", "").replace("http://", "").rstrip('/')

    # 2. Configure Client TLS Fingerprint Rotation (uTLS) and aligned User-Agent
    fingerprints = {
        "chrome": {
            "fingerprint": "chrome",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        },
        "firefox": {
            "fingerprint": "firefox",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        },
        "safari": {
            "fingerprint": "safari",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15"
        },
        "edge": {
            "fingerprint": "edge",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
        }
    }

    env_fp = os.environ.get("GOST_FINGERPRINT", "").lower()
    if env_fp in fingerprints:
        selected_fp = env_fp
        print(f"[+] Using configured TLS fingerprint from environment: {selected_fp}")
    else:
        selected_fp = random.choice(list(fingerprints.keys()))
        print(f"[+] Rotating TLS fingerprint (selected: {selected_fp})")

    fp_config = fingerprints[selected_fp]
    fingerprint = fp_config["fingerprint"]
    ua = fp_config["ua"]

    encoded_ua = urllib.parse.quote(f"User-Agent:{ua}")

    # Determine connection protocol, port, path, and fingerprint based on transport type
    if ":" in clean_url:
        host_port = clean_url
    else:
        if transport == "ws":
            host_port = f"{clean_url}:80"
        else:
            host_port = f"{clean_url}:443"

    if transport == "ws":
        # Plain Multiplexed WebSocket (no TLS / no fingerprint)
        ws_url = f"relay+mws://{auth}@{host_port}?path=/gost-bridge&header={encoded_ua}"
    else:
        # Default: relay+mwss (Multiplexed Secure WebSocket TLS)
        ws_url = f"relay+mwss://{auth}@{host_port}?path=/gost-bridge&header={encoded_ua}&fingerprint={fingerprint}"

    cmd = ["gost"]

    if proxy_enabled:
        cmd.extend(["-L", "socks5://127.0.0.1:1080?bypass=::/0"])
        print("[+] Creating local SOCKS5 proxy on port 1080 (IPv6 bypassed/rejected)")

    ssh_port = 2222
    if ssh_enabled:
        cmd.extend(["-L", f"tcp://127.0.0.1:{ssh_port}/127.0.0.1:2222"])
        print(f"[+] Forwarding local port {ssh_port} to container SSH (2222)")

    if local_forward:
        parts = local_forward.split(":")
        if len(parts) == 3:
            lp, rh, rp = parts[0], parts[1], parts[2]
            cmd.extend(["-L", f"tcp://127.0.0.1:{lp}/{rh}:{rp}"])
            print(f"[+] Forwarding local port {lp} to {rh}:{rp}")
            if rp == "2222":
                try:
                    ssh_port = int(lp)
                except ValueError:
                    pass
        else:
            cmd.extend(["-L", local_forward])
            print(f"[+] Forwarding custom rule: {local_forward}")

    cmd.extend(["-F", ws_url])

    print(f"[+] Launching GOST client -> {ws_url}")

    if ssh_enabled:
        try:
            stdout_dest = None if common.DEBUG_MODE else subprocess.DEVNULL
            stderr_dest = None if common.DEBUG_MODE else subprocess.DEVNULL
            proc = subprocess.Popen(cmd, stdout=stdout_dest, stderr=stderr_dest)
            # Wait for GOST to bind the local port (up to 10s)
            print(f"[+] Waiting for GOST to bind local port {ssh_port}...", end="", flush=True)
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    with _socket.create_connection(("127.0.0.1", ssh_port), timeout=0.5):
                        pass
                    print(" ready.")
                    break
                except OSError:
                    print(".", end="", flush=True)
                    time.sleep(0.5)
            else:
                print(f"\n[-] Timed out waiting for GOST to bind port {ssh_port}.")
                proc.terminate()
                sys.exit(1)

            run_ssh_fn(ssh_port)
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
