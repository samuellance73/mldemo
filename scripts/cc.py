import argparse
import sys
import os
import time

# Ensure the scripts directory is in sys.path so cc_utils can be imported properly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cc_utils.common as common
from cc_utils.common import get_node_url
from cc_utils.playit import start_playit_bridge
from cc_utils.chisel import run_chisel_client

def main():
    parser = argparse.ArgumentParser(
        description="Sanctuary Tunnel CLI (scripts/cc.py) - Connection Manager ONLY",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Connection protocol mode")
    
    # Playit-gg (minecraft mode) subparser
    playit_parser = subparsers.add_parser("playit", help="Establish direct TCP connection via Playit.gg (with XOR and MC Handshake)")
    playit_parser.add_argument("--host", required=True, help="Playit public tunnel host (e.g., south-forests.gl.at.ply.gg)")
    playit_parser.add_argument("--port", type=int, required=True, help="Playit public tunnel port (e.g., 43345)")
    playit_parser.add_argument("--local-port", type=int, default=2222, help="Local listening port for standard SSH connection (default: 2222)")

    # Chisel subparser
    chisel_parser = subparsers.add_parser("chisel", help="Establish HTTP/WebSocket tunnel via Chisel proxy to Hugging Face Space")
    chisel_parser.add_argument("--node", required=True, help="Name of the node to connect to (e.g., server-04)")
    chisel_parser.add_argument("--auth", default="user:apple123", help="Chisel authentication credentials (default: user:apple123)")
    chisel_parser.add_argument("--remotes", default="1080:socks 2222:127.0.0.1:2222 9000:127.0.0.1:9000", help="Chisel remotes to forward (default: SOCKS5 on 1080, SSH on 2222, Filebrowser on 9000)")

    args = parser.parse_args()
    
    # Set the global debug flag in common
    common.DEBUG_MODE = args.debug
    
    if args.mode == "playit":
        bridge = start_playit_bridge(args.host, args.port, args.local_port)
        print("====================================================================")
        print("                 PLAYIT TUNNEL READY TO USE")
        print("====================================================================")
        print(f"  SSH:  ssh -o StrictHostKeyChecking=no user@127.0.0.1 -p {args.local_port}")
        print(f"  SFTP: sftp -P {args.local_port} user@127.0.0.1")
        print("====================================================================")
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
        run_chisel_client(hf_url, args.auth, args.remotes)

if __name__ == "__main__":
    main()
