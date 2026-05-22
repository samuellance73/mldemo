import argparse
import sys
import os
import time
import subprocess

# Repo root on sys.path so top-level client/ package resolves (not scripts/client/)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

import client.common as common
from client.common import get_node_url
from client.playit_client import start_playit_bridge, run_probe
from client.chisel_client import run_chisel_client
from client.gost_client import run_gost_client
from client import ligolo_client
import client.node as node_cmd


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

    # Ligolo-ng subparser
    ligolo_parent = argparse.ArgumentParser(add_help=False)
    ligolo_parent.add_argument(
        "--proxy-bin",
        metavar="PATH",
        help="Local ligolo proxy binary (default: PATH, LIGOLO_PROXY, then download)",
    )
    ligolo_parent.add_argument(
        "--agent-bin",
        metavar="PATH",
        help="Local ligolo agent binary (default: PATH, LIGOLO_AGENT, then download)",
    )

    ligolo_parser = subparsers.add_parser(
        "ligolo",
        help="Ligolo-ng TUN pivoting (hub proxy on Space or local proxy)",
    )
    ligolo_sub = ligolo_parser.add_subparsers(dest="ligolo_mode", required=True)

    hub_parser = ligolo_sub.add_parser(
        "hub",
        parents=[ligolo_parent],
        help="Hub mode: agents connect to HF Space /tensor-mesh",
    )
    hub_parser.add_argument(
        "--node", required=True, help="Node name from state.json (e.g., server-01)"
    )
    hub_parser.add_argument(
        "--info",
        action="store_true",
        help="Print agent connect URL and fingerprint hints",
    )
    hub_parser.add_argument(
        "--fetch",
        action="store_true",
        help="Try to read fingerprint from container via SSH on :2222",
    )
    hub_parser.add_argument(
        "--via",
        choices=["chisel", "gost"],
        default="chisel",
        help="Tunnel for -L port forward (default: chisel)",
    )
    hub_parser.add_argument(
        "-L",
        dest="local_forward",
        help="Port forward via chisel/gost (e.g., 6801:127.0.0.1:6801 for Web UI)",
    )
    hub_parser.add_argument(
        "--auth",
        default="user:apple123",
        help="GOST auth when --via gost (default: user:apple123)",
    )
    hub_parser.add_argument(
        "--transport",
        default="mwss",
        choices=["mwss", "ws"],
        help="GOST transport when --via gost",
    )
    hub_parser.add_argument(
        "--socks",
        metavar="IP:PORT",
        help="SOCKS5 for agent command hint (ligolo agent --socks)",
    )

    local_parser = ligolo_sub.add_parser(
        "local",
        parents=[ligolo_parent],
        help="Local mode: run ligolo proxy on this workstation",
    )
    local_sub = local_parser.add_subparsers(dest="local_action", required=True)
    local_sub.add_parser(
        "start",
        parents=[ligolo_parent],
        help="Run local ligolo proxy (uses installed binary when available)",
    )
    agent_cmd_parser = local_sub.add_parser(
        "agent-cmd",
        parents=[ligolo_parent],
        help="Print agent connect command for local proxy",
    )
    agent_cmd_parser.add_argument(
        "--host",
        default=None,
        help="Override connect host (default: https://127.0.0.1:11601)",
    )
    agent_cmd_parser.add_argument(
        "--ignore-cert",
        action="store_true",
        help="Print -ignore-cert instead of fingerprint placeholder",
    )

    # Node subparser — HF Space lifecycle management
    node_parser = subparsers.add_parser(
        "node",
        help="Manage Hugging Face Space nodes (status, restart, wake, sleep, vars)",
    )
    node_parser.add_argument(
        "name",
        help="Node name from nodes.yaml (e.g., server-01) or 'all'",
    )
    node_action = node_parser.add_mutually_exclusive_group(required=True)
    node_action.add_argument(
        "--status", action="store_true",
        help="Show runtime status and hardware for the node(s)",
    )
    node_action.add_argument(
        "--restart", action="store_true",
        help="Trigger a Space restart",
    )
    node_action.add_argument(
        "--wake", action="store_true",
        help="Resume a sleeping/paused Space",
    )
    node_action.add_argument(
        "--sleep", action="store_true",
        help="Pause the Space to save compute quota",
    )
    node_action.add_argument(
        "--vars", action="store_true",
        help="List public Space variables",
    )
    node_action.add_argument(
        "--secrets", action="store_true",
        help="List secret key names currently set on the Space (values are never exposed)",
    )
    node_action.add_argument(
        "--set-var", metavar="KEY=VALUE",
        help="Set a public Space variable (e.g., --set-var LOG_LEVEL=2)",
    )
    node_action.add_argument(
        "--del-var", metavar="KEY",
        help="Delete a public Space variable",
    )
    node_action.add_argument(
        "--logs", action="store_true",
        help="Snapshot the latest app container logs",
    )
    node_action.add_argument(
        "--build-logs", action="store_true",
        help="Snapshot the latest build/Docker logs",
    )
    node_action.add_argument(
        "--dev", action="store_true",
        help="Enable Space Dev Mode (pauses app, opens persistent SSH shell into container)",
    )
    node_action.add_argument(
        "--undev", action="store_true",
        help="Disable Space Dev Mode and return to normal operation",
    )
    node_parser.add_argument(
        "--follow", "-f", action="store_true",
        help="Stream logs continuously (use with --logs or --build-logs)",
    )

    args = parser.parse_args()

    # Set the global debug flag in common
    common.DEBUG_MODE = args.debug

    if args.mode == "ligolo":
        ligolo_client.set_bins(
            proxy_bin=getattr(args, "proxy_bin", None),
            agent_bin=getattr(args, "agent_bin", None),
        )
        if args.ligolo_mode == "hub":
            try:
                hf_url = get_node_url(args.node)
            except Exception as e:
                print(f"[-] Error: {e}", file=sys.stderr)
                sys.exit(1)
            if args.local_forward:
                ligolo_client.run_hub_forward(
                    hf_url,
                    args.via,
                    args.local_forward,
                    args.auth,
                    args.transport,
                    run_ssh,
                )
                sys.exit(0)
            if args.info or args.fetch or not args.local_forward:
                ligolo_client.print_hub_info(
                    hf_url,
                    args.node,
                    fetch=args.fetch,
                    agent_bin=getattr(args, "agent_bin", None),
                )
                if args.socks:
                    print(f"  Optional: --socks {args.socks}")
                sys.exit(0)
        elif args.ligolo_mode == "local":
            if args.local_action == "start":
                ligolo_client.run_local_start(
                    proxy_bin=getattr(args, "proxy_bin", None),
                )
            elif args.local_action == "agent-cmd":
                ligolo_client.print_local_agent_cmd(
                    host=args.host,
                    ignore_cert=args.ignore_cert,
                    agent_bin=getattr(args, "agent_bin", None),
                )
        sys.exit(0)

    # Node subcommand — handled entirely separately, no tunnel flags needed
    if args.mode == "node":
        if args.status:
            node_cmd.cmd_status(args.name)
        elif args.restart:
            node_cmd.cmd_restart(args.name)
        elif args.wake:
            node_cmd.cmd_wake(args.name)
        elif args.sleep:
            node_cmd.cmd_sleep(args.name)
        elif args.vars:
            node_cmd.cmd_vars(args.name)
        elif args.secrets:
            node_cmd.cmd_secrets(args.name)
        elif args.set_var:
            node_cmd.cmd_vars(args.name, set_kv=args.set_var)
        elif args.del_var:
            node_cmd.cmd_vars(args.name, delete_key=args.del_var)
        elif args.logs:
            node_cmd.cmd_logs(args.name, follow=args.follow, build=False)
        elif args.build_logs:
            node_cmd.cmd_logs(args.name, follow=args.follow, build=True)
        elif args.dev:
            node_cmd.cmd_dev(args.name, disable=False)
        elif args.undev:
            node_cmd.cmd_dev(args.name, disable=True)
        sys.exit(0)

    # Action flags verification (tunnel modes only)
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
            cmd = ["chisel", "client", server_url] + remotes_list
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
            run_chisel_client(hf_url, remotes_str)

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
