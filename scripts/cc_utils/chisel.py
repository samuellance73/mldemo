import subprocess
import sys

def run_chisel_client(hf_url, auth, remotes):
    server_url = hf_url.rstrip('/') + '/chisel-tunnel'
    print(f"[+] Launching Chisel client -> {server_url}")
    print(f"[+] Forwarding: {remotes}")
    
    cmd = ["chisel", "client", "--auth", auth, server_url] + remotes.split()
    try:
        # Run chisel client in foreground
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[+] Chisel client stopped.")
    except FileNotFoundError:
        print("[-] Error: 'chisel' binary not found. Please install it from https://github.com/jpillora/chisel", file=sys.stderr)
        sys.exit(1)
