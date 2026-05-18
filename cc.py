import sys
import socket
import threading
import subprocess
import time
import argparse
import os

XOR_KEY = 0x5A  # Must match the key on the server (wrapper.py)
LOCAL_PORT = 2222

def pipe_xor(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            # XOR every byte in transit to scramble/unscramble it
            scrambled = bytes([b ^ XOR_KEY for b in data])
            dst.sendall(scrambled)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def pack_varint(val):
    out = b''
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out += bytes([byte | 0x80])
        else:
            out += bytes([byte])
            break
    return out

def build_mc_handshake(host, port):
    host_bytes = host.encode('utf-8')
    # Packet ID (0x00) + Protocol (763) + Host Len + Host + Port (2 bytes) + Next State (2 for Login)
    data = pack_varint(0) + pack_varint(763) + pack_varint(len(host_bytes)) + host_bytes + port.to_bytes(2, 'big') + pack_varint(2)
    # Prefix with total packet length
    return pack_varint(len(data)) + data

class CommandCenterCLI:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.local_port = LOCAL_PORT
        self.xor_key = XOR_KEY

    def bridge_loop(self, local_server):
        while True:
            try:
                client_sock, addr = local_server.accept()
                try:
                    # Connect to Playit's public address
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.connect((self.host, self.port))
                    
                    # FAKE GAME HEADER: Send dynamic Minecraft Handshake matching the exact Playit domain
                    mc_handshake = build_mc_handshake(self.host, self.port)
                    remote_sock.sendall(mc_handshake)
                    
                    # Spawn bidirectional pipes
                    threading.Thread(target=pipe_xor, args=(client_sock, remote_sock), daemon=True).start()
                    threading.Thread(target=pipe_xor, args=(remote_sock, client_sock), daemon=True).start()
                except Exception as e:
                    print(f"\n[-] Failed to establish connection to remote tunnel: {e}")
                    try: client_sock.close()
                    except: pass
            except Exception:
                break

    def start_xor_bridge(self):
        """Background stealth XOR bridge."""
        local_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            local_server.bind(("127.0.0.1", self.local_port))
            local_server.listen(5)
            print(f"[*] Stealth XOR bridge listening locally on 127.0.0.1:{self.local_port}")
            print(f"[*] Forwarding obfuscated traffic to {self.host}:{self.port}")
            
            # Start the bridge accept loop in a background daemon thread
            bridge_thread = threading.Thread(target=self.bridge_loop, args=(local_server,), daemon=True)
            bridge_thread.start()
            return local_server
        except Exception as e:
            print(f"[-] Error starting local bridge: {e}")
            sys.exit(1)

    def cmd_ssh(self):
        """Automates stealth bridge and interactive SSH session."""
        print("[*] Initializing encrypted XOR bridge...", flush=True)
        local_server = self.start_xor_bridge()
        time.sleep(0.5)
        print("[*] Launching resilient SSH session...", flush=True)
        subprocess.run(["ssh", "-o", "ServerAliveInterval=3", "user@127.0.0.1", "-p", str(self.local_port)])
        print("[*] SSH session ended. Closing bridge.")
        local_server.close()

    def cmd_sftp(self, mount_point="./remote_space"):
        """Mounts remote Space filesystem locally via SSHFS."""
        print("[*] Initializing encrypted XOR bridge...", flush=True)
        local_server = self.start_xor_bridge()
        time.sleep(0.5)
        print(f"[*] Mounting remote container filesystem to {mount_point}...", flush=True)
        subprocess.run(["mkdir", "-p", mount_point])
        res = subprocess.run(["sshfs", "user@127.0.0.1:/home/user", mount_point, "-p", str(self.local_port)])
        if res.returncode == 0:
            print(f"[+] Filesystem mounted successfully at '{mount_point}'.")
            print("[*] The XOR bridge will remain open in the background to service filesystem requests.")
            print("[*] Press Ctrl+C to unmount and exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n[*] Unmounting {mount_point} and closing bridge...")
                subprocess.run(["fusermount", "-u", mount_point])
                local_server.close()
        else:
            print("[-] Failed to mount filesystem.")
            local_server.close()

    def cmd_backup(self, dest="./space_backup.tar.gz"):
        """Pulls instantaneous compressed snapshot of remote persistent data."""
        print("[*] Initializing encrypted XOR bridge...", flush=True)
        local_server = self.start_xor_bridge()
        time.sleep(0.5)
        print("[*] Initiating zero-downtime remote data snapshot...", flush=True)
        cmd = f"ssh -p {self.local_port} user@127.0.0.1 'tar -czf - /data/mc /home/user/.torch_metrics 2>/dev/null' > {dest}"
        res = subprocess.run(cmd, shell=True)
        if res.returncode == 0:
            print(f"[+] Backup successfully downloaded to {dest}")
        else:
            print(f"[-] Backup encountered an error (code {res.returncode})")
        local_server.close()

    def cmd_status(self):
        """Queries Space Telemetry & container health."""
        print("[*] Initializing encrypted XOR bridge...", flush=True)
        local_server = self.start_xor_bridge()
        time.sleep(0.5)
        print("[*] Querying remote container telemetry...", flush=True)
        script = (
            "echo '=== CONTAINER UPTIME & LOAD ==='; uptime; "
            "echo ''; echo '=== MEMORY USAGE ==='; free -h; "
            "echo ''; echo '=== DISK USAGE ==='; df -h /home/user /data 2>/dev/null || df -h /home/user; "
            "echo ''; echo '=== COVERT SERVICES STATUS ==='; "
            "ps aux | grep -v grep | grep -E 'python-cache-manager|ai-metrics-collector|tensor-allocator|sshd|mc_daemon'"
        )
        subprocess.run(["ssh", "-p", str(self.local_port), "user@127.0.0.1", script])
        local_server.close()

    def cmd_mc_console(self):
        """Opens Local Interactive Minecraft Server Console via SSH/tmux."""
        print("[*] Initializing encrypted XOR bridge...", flush=True)
        local_server = self.start_xor_bridge()
        time.sleep(0.5)
        print("[*] Attaching to remote Minecraft tmux console...", flush=True)
        subprocess.run(["ssh", "-t", "-p", str(self.local_port), "user@127.0.0.1", "tmux attach -t mc_server || echo '[-] tmux session mc_server not found. Is mc_daemon running with tmux?'"])
        local_server.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Command Center Unified Automation CLI (cc.py)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "action", 
        choices=["ssh", "sftp", "backup", "status", "mc-console"], 
        help=(
            "Action to execute:\n"
            "  ssh        - Establishes XOR stealth bridge & spawns interactive SSH\n"
            "  sftp       - Mounts remote Space filesystem locally via SSHFS\n"
            "  backup     - Pulls instant compressed snapshot of remote /data and logs\n"
            "  status     - Queries remote container telemetry, memory, and service health\n"
            "  mc-console - Attaches to remote Minecraft server tmux console"
        )
    )
    parser.add_argument("--host", required=True, help="Playit public tunnel host (e.g., south-forests.gl.at.ply.gg)")
    parser.add_argument("--port", type=int, required=True, help="Playit public tunnel port (e.g., 43345)")
    parser.add_argument("--mount", default="./remote_space", help="Local mount directory for sftp action (default: ./remote_space)")
    parser.add_argument("--backup-dest", default="./space_backup.tar.gz", help="Destination file for backup action (default: ./space_backup.tar.gz)")
    
    args = parser.parse_args()
    cli = CommandCenterCLI(args.host, args.port)
    
    if args.action == "ssh":
        cli.cmd_ssh()
    elif args.action == "sftp":
        cli.cmd_sftp(mount_point=args.mount)
    elif args.action == "backup":
        cli.cmd_backup(dest=args.backup_dest)
    elif args.action == "status":
        cli.cmd_status()
    elif args.action == "mc-console":
        cli.cmd_mc_console()
