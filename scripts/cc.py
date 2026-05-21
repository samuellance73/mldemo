import argparse
import sys
import os
import time
import subprocess

# Ensure the scripts directory is in sys.path so cc_utils can be imported properly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cc_utils.common as common
from cc_utils.common import get_node_url
from cc_utils.playit import start_playit_bridge, run_probe
from cc_utils.chisel import run_chisel_client
from cc_utils.gost import run_gost_client


def run_ssh(port):
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",  # Prevents key mismatch lockouts
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=1",
        "user@127.0.0.1",
        "-p", str(port),
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

    # Common parent parser for standardized action flags
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-s", "--ssh", action="store_true", help="Automatically spawn SSH connection through the established tunnel"
    )
    common_parser.add_argument(
        "-p", "--proxy", action="store_true", help="Spawn SOCKS5 proxy on port 1080"
    )
    common_parser.add_argument(
        "-L", dest="local_forward", help="Local port forwarding (e.g., 31337:127.0.0.1:31337)"
    )

    subparsers = parser.add_subparsers(
        dest="mode", required=True, help="Connection protocol mode"
    )

    # Playit-gg (minecraft mode) subparser
    playit_parser = subparsers.add_parser(
        "playit",
        parents=[common_parser],
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
        default=25565,
        help="Public Playit relay port from playit.gg (default: 25565). "
        "Not the local SSH port (2222).",
    )
    playit_parser.add_argument(
        "--probe",
        action="store_true",
        help="Ping the tunnel path (TCP + SSH banner check) and exit",
    )
    playit_parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain TCP bridge (no MC handshake, no XOR). Use with playit TCP tunnel → 127.0.0.1:2222",
    )

    # Chisel subparser
    chisel_parser = subparsers.add_parser(
        "chisel",
        parents=[common_parser],
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

    # GOST subparser
    gost_parser = subparsers.add_parser(
        "gost",
        parents=[common_parser],
        help="Establish HTTP/WebSocket tunnel via GOST proxy to Hugging Face Space",
    )
    gost_parser.add_argument(
        "--node", required=True, help="Name of the node to connect to (e.g., server-04)"
    )
    gost_parser.add_argument(
        "--auth",
        default="user:apple123",
        help="GOST authentication credentials (default: user:apple123)",
    )
    gost_parser.add_argument(
        "--transport",
        default="mwss",
        choices=["mwss", "ws"],
        help="GOST transport protocol: 'mwss' (multiplexed secure WebSocket, default) or 'ws' (plain multiplexed WebSocket)",
    )

    args = parser.parse_args()

    # Set the global debug flag in common
    common.DEBUG_MODE = args.debug

    # Action flags verification
    if args.mode == "playit" and getattr(args, "probe", False):
        pass
    else:
        if not (args.ssh or args.proxy or args.local_forward):
            parser.error("At least one action flag must be specified: -s/--ssh, -p/--proxy, or -L <forward_rule>")

    if args.mode == "playit":
        if args.probe:
            sys.exit(run_probe(args.host, args.port, plain=args.plain))

        if args.proxy:
            print("[-] Error: SOCKS5 proxy mode (-p/--proxy) is not supported for playit mode. Use chisel or gost instead.", file=sys.stderr)
            sys.exit(1)

        # Determine local port and remote target port to listen on
        local_port = 2222
        remote_target_port = 2222
        if args.local_forward:
            parts = args.local_forward.split(":")
            try:
                local_port = int(parts[0])
                if len(parts) >= 3:
                    remote_target_port = int(parts[2])
                elif len(parts) == 1:
                    remote_target_port = local_port
            except (ValueError, IndexError):
                print(f"[-] Error: Invalid local forward format: '{args.local_forward}'. Expected local_port:remote_host:remote_port or local_port", file=sys.stderr)
                sys.exit(1)

        bridge = start_playit_bridge(
            args.host, args.port, local_port, remote_target_port=remote_target_port, plain=args.plain
        )
        print("====================================================================")
        print("                 PLAYIT TUNNEL READY TO USE")
        print("====================================================================")
        mode = "plain TCP" if args.plain else "MC login + plugin tunnel"
        print(f"  Relay:  {args.host}:{args.port}  ({mode})")
        if args.ssh:
            run_ssh(local_port)
            print("\n[+] Closing Playit XOR bridge.")
            bridge.close()
        else:
            print(
                f"  SSH:  ssh -o StrictHostKeyChecking=no user@127.0.0.1 -p {local_port}"
            )
            print(f"  SFTP: sftp -P {local_port} user@127.0.0.1")
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

        # Build Chisel remotes list based on active flags
        remotes_list = []
        if args.ssh:
            remotes_list.append("2222:127.0.0.1:2222")
        if args.proxy:
            remotes_list.append("1080:socks")
        if args.local_forward:
            remotes_list.append(args.local_forward)

        remotes_str = " ".join(remotes_list)

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
            ] + remotes_list
            print(f"[+] Launching Chisel client in background -> {server_url}")
            print(f"[+] Forwarding: {remotes_str}")
            try:
                proc = subprocess.Popen(
                    cmd, stdout=None, stderr=None
                )
            except FileNotFoundError:
                print(
                    "[-] Error: 'chisel' binary not found. Please install Chisel from https://github.com/jpillora/chisel",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Wait for connection
            time.sleep(2)

            # Determine SSH port from local forward or default 2222
            ssh_port = 2222
            if args.local_forward:
                parts = args.local_forward.split(":")
                if len(parts) >= 3 and parts[2] == "2222":
                    try:
                        ssh_port = int(parts[0])
                    except ValueError:
                        pass

            run_ssh(ssh_port)
            print("[+] Terminating Chisel client.")
            proc.terminate()
            proc.wait()
        else:
            run_chisel_client(hf_url, args.auth, remotes_str)

    elif args.mode == "gost":
        try:
            hf_url = get_node_url(args.node)
        except Exception as e:
            print(f"[-] Error: {e}", file=sys.stderr)
            sys.exit(1)

        print("====================================================================")
        print("                 GOST TUNNEL INITIALIZING")
        print("====================================================================")

        run_gost_client(hf_url, args.auth, args.ssh, args.proxy, args.local_forward, run_ssh, args.transport)


if __name__ == "__main__":
    main()
