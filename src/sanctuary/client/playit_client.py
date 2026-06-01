import socket
import sys
import threading

from sanctuary.client import mc_tunnel
from sanctuary.client.common import log_debug, log_error, log_info, pipe


def probe_relay(host, port, timeout=5.0):
    last_err = None
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
            for af, _, _, _, addr in infos:
                sock = socket.socket(af, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                try:
                    sock.connect(addr)
                    return True, addr
                except OSError as e:
                    last_err = e
                finally:
                    sock.close()
        except socket.gaierror as e:
            last_err = e
    return False, last_err


def run_probe(host, port, plain=False):
    print(f"[*] Probing {host}:{port} ...")
    ok, addr = probe_relay(host, port)
    if not ok:
        print(f"  [FAIL] relay_tcp: cannot connect to {host}:{port} ({addr})")
        return 1
    print(f"  [OK] relay_tcp: connected to {addr}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(addr)
        if not plain:
            sock.sendall(mc_tunnel.build_handshake(host, port))
            sock.sendall(mc_tunnel.build_login_start())
            reader = mc_tunnel.PacketReader(sock)
            while True:
                pkt_id, payload = reader.read_packet()
                if pkt_id == mc_tunnel.PKT_LOGIN_SUCCESS:
                    break
                if pkt_id == mc_tunnel.PKT_LOGIN_PLUGIN_REQUEST:
                    mid, _ = mc_tunnel.read_varint_from_buf(payload, 0)
                    sock.sendall(mc_tunnel.frame_login_plugin_response(mid, b""))
            sock.sendall(
                mc_tunnel.wrap_tunnel_client(
                    mc_tunnel.xor_bytes(b"SSH-2.0-cc-probe\r\n")
                )
            )

            while True:
                pkt_id, payload = reader.read_packet()
                if pkt_id == mc_tunnel.PKT_LOGIN_PLUGIN_REQUEST:
                    chunk, _ = mc_tunnel.extract_tunnel_from_request(payload)
                    if chunk and chunk.startswith(b"SSH-2.0"):
                        banner = chunk.splitlines()[0].decode(errors="replace")
                        print(f"  [OK] ssh_banner: {banner}")
                        return 0
        else:
            sock.sendall(b"SSH-2.0-cc-probe\r\n")
            raw = sock.recv(256)
            if raw and raw.startswith(b"SSH-2.0"):
                banner = raw.splitlines()[0].decode(errors="replace")
                print(f"  [OK] ssh_banner: {banner}")
                return 0
        print("  [FAIL] ssh_banner: invalid or empty response")
        return 1
    except Exception as e:
        print(f"  [FAIL] tunnel_path: {e}")
        return 1
    finally:
        sock.close()


def _bridge_loop(local_server, handler, host, port, remote_target_port):
    while True:
        try:
            client_sock, addr = local_server.accept()
            threading.Thread(
                target=handler,
                args=(client_sock, addr, host, port, remote_target_port),
                daemon=True,
            ).start()
        except Exception:
            break


def handle_client(client_sock, client_addr, host, port, remote_target_port):
    log_debug(f"Accepted local connection from {client_addr[0]}:{client_addr[1]}")
    remote_sock = None
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(10.0)
        remote_sock.connect((host, port))
        reader = mc_tunnel.client_login(remote_sock, host, port, remote_target_port)
        remote_sock.settimeout(None)
        mc_tunnel.relay_client(reader, client_sock, remote_sock)
    except Exception as e:
        log_debug(f"Tunnel failed for {client_addr[0]}:{client_addr[1]}: {e}")
        for s in (client_sock, remote_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass


def handle_client_plain(client_sock, client_addr, host, port, remote_target_port):
    log_debug(f"Accepted local connection from {client_addr[0]}:{client_addr[1]}")
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(10.0)
        remote_sock.connect((host, port))
        remote_sock.settimeout(None)
        threading.Thread(
            target=pipe,
            args=(client_sock, remote_sock),
            kwargs={"xor": False, "label": f"Local({client_addr[1]}) -> Remote"},
            daemon=True,
        ).start()
        threading.Thread(
            target=pipe,
            args=(remote_sock, client_sock),
            kwargs={"xor": False, "label": f"Remote -> Local({client_addr[1]})"},
            daemon=True,
        ).start()
    except Exception as e:
        log_debug(f"Tunnel failed: {e}")
        try:
            client_sock.close()
        except OSError:
            pass


def start_playit_bridge(host, port, local_port, remote_target_port=2222, plain=False):
    ok, probe_result = probe_relay(host, port)
    if not ok:
        log_error(f"Cannot reach Playit relay {host}:{port}: {probe_result}")
        sys.exit(1)

    local_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    handler = handle_client_plain if plain else handle_client
    try:
        local_server.bind(("127.0.0.1", local_port))
        local_server.listen(10)
        if plain:
            log_info(f"Playit plain bridge 127.0.0.1:{local_port} -> {host}:{port}")
        else:
            log_info(
                f"Playit MC-disguised bridge 127.0.0.1:{local_port} -> {host}:{port}"
            )
            log_info(
                f"Traffic: SSH -> XOR -> Login Plugin ({mc_tunnel.TUNNEL_CHANNEL})"
            )
            log_info(f"playit.gg local target: 127.0.0.1:{remote_target_port}")

        threading.Thread(
            target=_bridge_loop,
            args=(local_server, handler, host, port, remote_target_port),
            daemon=True,
        ).start()
        return local_server
    except Exception as e:
        log_error(f"Error starting bridge: {e}")
        sys.exit(1)
