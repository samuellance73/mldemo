import socket
import threading
import sys
from cc_utils.common import pipe_xor, build_mc_handshake, log_debug, log_info, log_error


def bridge_loop(local_server, host, port):
    while True:
        try:
            client_sock, addr = local_server.accept()
            # Start thread to connect to Playit and perform handshake
            threading.Thread(
                target=handle_client, args=(client_sock, addr, host, port), daemon=True
            ).start()
        except Exception:
            break


def handle_client(client_sock, client_addr, host, port):
    log_info(f"Accepted local connection from {client_addr[0]}:{client_addr[1]}")
    try:
        log_debug(f"Connecting to remote playit tunnel {host}:{port}...")
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(10.0)  # 10s connection timeout
        remote_sock.connect((host, port))
        remote_sock.settimeout(None)  # Reset timeout for streaming
        log_debug("Connected to remote tunnel. Sending Minecraft Handshake...")

        # Send Minecraft Handshake matching the Playit address
        mc_handshake = build_mc_handshake(host, port)
        remote_sock.sendall(mc_handshake)
        log_debug("Minecraft Handshake sent. Initializing XOR pipes...")

        # Spawn bidirectional pipes with debug labels
        threading.Thread(
            target=pipe_xor,
            args=(client_sock, remote_sock, f"Local({client_addr[1]}) -> Remote"),
            daemon=True,
        ).start()
        threading.Thread(
            target=pipe_xor,
            args=(remote_sock, client_sock, f"Remote -> Local({client_addr[1]})"),
            daemon=True,
        ).start()
    except Exception as e:
        log_error(
            f"Connection to remote tunnel failed for client {client_addr[0]}:{client_addr[1]}: {e}"
        )
        try:
            client_sock.close()
        except:
            pass


def start_playit_bridge(host, port, local_port):
    local_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        local_server.bind(("127.0.0.1", local_port))
        local_server.listen(10)
        log_info(f"Playit XOR Bridge listening on 127.0.0.1:{local_port}")
        log_info(f"Forwarding traffic to {host}:{port}")

        bridge_thread = threading.Thread(
            target=bridge_loop, args=(local_server, host, port), daemon=True
        )
        bridge_thread.start()
        return local_server
    except Exception as e:
        log_error(f"Error starting local bridge: {e}")
        sys.exit(1)
