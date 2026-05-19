import argparse
import sys
import os
import time
import subprocess

# Ensure the scripts directory is in sys.path so cc_utils can be imported properly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cc_utils.common as common
from cc_utils.common import get_node_url
from cc_utils.playit import start_playit_bridge
from cc_utils.chisel import run_chisel_client


def run_ssh(port):
    ssh_cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=0",
        "-o",
        "ServerAliveInterval=2",
        "-o",
        "ServerAliveCountMax=99999",
        "user@127.0.0.1",
        "-p",
        str(port),
    ]
    print(f"[+] Spawning SSH session: {' '.join(ssh_cmd)}")
    try:
        subprocess.run(ssh_cmd)
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Sanctuary Tunnel CLI (scripts/cc.py) - Connection Manager ONLY",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose debug logging"
    )

    subparsers = parser.add_subparsers(
        dest="mode", required=True, help="Connection protocol mode"
    )

    # Playit-gg (minecraft mode) subparser
    playit_parser = subparsers.add_parser(
        "playit",
        help="Establish direct TCP connection via Playit.gg (with XOR and MC Handshake)",
    )
    playit_parser.add_argument(
        "--host",
        required=True,
        help="Playit public tunnel host (e.g., south-forests.gl.at.ply.gg)",
    )
    playit_parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Playit public tunnel port (e.g., 43345)",
    )
    playit_parser.add_argument(
        "--local-port",
        type=int,
        default=2222,
        help="Local listening port for standard SSH connection (default: 2222)",
    )
    playit_parser.add_argument(
        "--ssh",
        action="store_true",
        help="Automatically spawn SSH connection through the established tunnel",
    )

    # Chisel subparser
    chisel_parser = subparsers.add_parser(
        "chisel",
        help="Establish HTTP/WebSocket tunnel via Chisel proxy to Hugging Face Space",
    )
    chisel_parser.add_argument(
        "--node", required=True, help="Name of the node to connect to (e.g., server-04)"
    )
    chisel_parser.add_argument(
        "--auth",
        default="user:apple123",
        help="Chisel authentication credentials (default: user:apple123)",
    )
    chisel_parser.add_argument(
        "--remotes",
        default="1080:socks 2222:127.0.0.1:2222 9000:127.0.0.1:9000",
        help="Chisel remotes to forward (default: SOCKS5 on 1080, SSH on 2222, Filebrowser on 9000)",
    )
    chisel_parser.add_argument(
        "--ssh",
        action="store_true",
        help="Automatically spawn SSH connection through the established tunnel",
    )

    args = parser.parse_args()

    # Set the global debug flag in common
    common.DEBUG_MODE = args.debug

    if args.mode == "playit":
        bridge = start_playit_bridge(args.host, args.port, args.local_port)
        print("====================================================================")
        print("                 PLAYIT TUNNEL READY TO USE")
        print("====================================================================")
        if args.ssh:
            run_ssh(args.local_port)
            print("\n[+] Closing Playit XOR bridge.")
            bridge.close()
        else:
            print(
                f"  SSH:  ssh -o StrictHostKeyChecking=no user@127.0.0.1 -p {args.local_port}"
            )
            print(f"  SFTP: sftp -P {args.local_port} user@127.0.0.1")
            print(
                "===================================================================="
            )
            print("Press Ctrl+C to stop the bridge and exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[+] Closing Playit XOR bridge.")
                bridge.close()

    elif args.mode == "chisel":
        try:
            hf_url = get_node_url(args.node)
        except Exception as e:
            print(f"[-] Error: {e}", file=sys.stderr)
            sys.exit(1)

        print("====================================================================")
        print("                 CHISEL TUNNEL INITIALIZING")
        print("====================================================================")
        if args.ssh:
            # Launch Chisel in background
            server_url = hf_url.rstrip("/") + "/chisel-tunnel"
            cmd = [
                "chisel",
                "client",
                "--auth",
                args.auth,
                server_url,
            ] + args.remotes.split()
            print(f"[+] Launching Chisel client in background -> {server_url}")
            print(f"[+] Forwarding: {args.remotes}")
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except FileNotFoundError:
                print(
                    "[-] Error: 'chisel' binary not found. Please install Chisel from https://github.com/jpillora/chisel",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Wait for connection
            time.sleep(2)

            # Determine SSH port from remotes
            ssh_port = 2222
            for part in args.remotes.split():
                if part.endswith(":2222") or ":127.0.0.1:2222" in part:
                    subparts = part.split(":")
                    if subparts:
                        try:
                            ssh_port = int(subparts[0])
                        except ValueError:
                            pass

            run_ssh(ssh_port)
            print("[+] Terminating Chisel client.")
            proc.terminate()
            proc.wait()
        else:
            run_chisel_client(hf_url, args.auth, args.remotes)


if __name__ == "__main__":
    main()
