import os
import socket
import sys
import threading

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))
from services import mc_tunnel  # noqa: E402

from cc_utils.common import log_debug, log_info, log_error, pipe_direct

_RST_HINT = (
    "Connection dropped after login — set playit.gg local target to 127.0.0.1:25565 "
    "and redeploy the container."
)


def probe_relay(host, port, timeout=8.0):
    last_err = None
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
        except socket.gaierror as e:
            last_err = e
            continue
        for af, _, _, _, addr in infos:
            sock = socket.socket(af, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect(addr)
                sock.close()
                return True, addr
            except OSError as e:
                last_err = e
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
    return False, last_err


def _connect_relay(host, port, timeout):
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    sock = socket.socket(infos[0][0], socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(infos[0][4])
    return sock


def probe_tunnel(host, port, timeout=12.0):
    steps = []
    ok, addr = probe_relay(host, port, timeout=timeout)
    if ok:
        steps.append(("relay_tcp", True, f"connected to {addr}"))
    else:
        steps.append(("relay_tcp", False, str(addr)))
        return steps, False

    sock = None
    try:
        sock = _connect_relay(host, port, timeout)
        sock.sendall(mc_tunnel.build_handshake(host, port))
        steps.append(("mc_handshake", True, "sent"))
        sock.sendall(mc_tunnel.build_login_start())
        steps.append(("mc_login_start", True, "sent"))
        reader = mc_tunnel.PacketReader(sock)
        sock.settimeout(timeout)
        while True:
            pkt_id, payload = reader.read_packet()
            if pkt_id == mc_tunnel.PKT_LOGIN_SUCCESS:
                break
            if pkt_id == mc_tunnel.PKT_LOGIN_PLUGIN_REQUEST:
                mid, _ = mc_tunnel.read_varint_from_buf(payload, 0)
                sock.sendall(mc_tunnel.frame_login_plugin_response(mid, b""))
        sock.settimeout(None)
        steps.append(("mc_login", True, "login success received"))
        sock.sendall(mc_tunnel.wrap_tunnel_client(mc_tunnel.xor_bytes(b"SSH-2.0-cc-probe\r\n")))
        sock.settimeout(timeout)
        ok, detail = False, "no SSH banner in plugin packets"
        try:
            while True:
                pkt_id, payload = reader.read_packet()
                if pkt_id == mc_tunnel.PKT_LOGIN_PLUGIN_REQUEST:
                    chunk, _ = mc_tunnel.extract_tunnel_from_request(payload)
                    if chunk and chunk.startswith(b"SSH-2.0"):
                        ok = True
                        detail = chunk.splitlines()[0].decode(errors="replace")
                        break
        except socket.timeout:
            detail = "no SSH banner (timeout)"
        steps.append(("ssh_banner", ok, detail))
        if not ok and ("reset" in detail.lower() or "104" in detail):
            steps.append(("hint", False, _RST_HINT))
        return steps, ok
    except OSError as e:
        steps.append(("tunnel_path", False, str(e)))
        if "104" in str(e) or "reset" in str(e).lower():
            steps.append(("hint", False, _RST_HINT))
        return steps, False
    finally:
        if sock:
            try:
                sock.close()
            except OSError:
                pass


def probe_tunnel_plain(host, port, timeout=10.0):
    steps = []
    ok, addr = probe_relay(host, port, timeout=timeout)
    if ok:
        steps.append(("relay_tcp", True, f"connected to {addr}"))
    else:
        steps.append(("relay_tcp", False, str(addr)))
        return steps, False

    sock = None
    try:
        sock = _connect_relay(host, port, timeout)
        steps.append(("plain_tcp", True, "no MC disguise"))
        probe_line = b"SSH-2.0-cc-probe\r\n"
        sock.sendall(probe_line)
        sock.settimeout(timeout)
        raw = sock.recv(256)
        if raw and raw.startswith(b"SSH-2.0"):
            steps.append(("ssh_banner", True, raw.splitlines()[0].decode(errors="replace")))
            return steps, True
        steps.append(("ssh_banner", False, f"got {len(raw)} bytes"))
        return steps, False
    except OSError as e:
        steps.append(("tunnel_path", False, str(e)))
        return steps, False
    finally:
        if sock:
            try:
                sock.close()
            except OSError:
                pass


def run_probe(host, port, plain=False):
    mode = "plain TCP" if plain else "MC login + plugin tunnel (bungeecord:main)"
    print(f"[*] Probing {host}:{port} ({mode}) ...")
    steps, ok = probe_tunnel_plain(host, port) if plain else probe_tunnel(host, port)
    for name, passed, detail in steps:
        mark = "OK" if passed else "FAIL"
        print(f"  [{mark}] {name}: {detail}")
    if ok:
        print("[+] Tunnel path looks healthy.")
        return 0
    print("[-] Probe failed.")
    return 1


def _bridge_loop(local_server, handler, host, port):
    while True:
        try:
            client_sock, addr = local_server.accept()
            threading.Thread(
                target=handler, args=(client_sock, addr, host, port), daemon=True
            ).start()
        except Exception:
            break


def handle_client(client_sock, client_addr, host, port):
    log_info(f"Accepted local connection from {client_addr[0]}:{client_addr[1]}")
    remote_sock = None
    try:
        log_debug(f"Connecting to playit {host}:{port}...")
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(15.0)
        remote_sock.connect((host, port))
        log_debug("MC login (handshake + login start + login success)...")
        reader = mc_tunnel.client_login(remote_sock, host, port)
        remote_sock.settimeout(None)
        log_debug("Relaying SSH inside Login Plugin packets (XOR + bungeecord:main)")
        mc_tunnel.relay_client(reader, client_sock, remote_sock)
    except Exception as e:
        log_error(f"Tunnel failed for {client_addr[0]}:{client_addr[1]}: {e}")
        for s in (client_sock, remote_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass


def handle_client_plain(client_sock, client_addr, host, port):
    log_info(f"Accepted local connection from {client_addr[0]}:{client_addr[1]}")
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.settimeout(10.0)
        remote_sock.connect((host, port))
        remote_sock.settimeout(None)
        threading.Thread(
            target=pipe_direct,
            args=(client_sock, remote_sock, f"Local({client_addr[1]}) -> Remote"),
            daemon=True,
        ).start()
        threading.Thread(
            target=pipe_direct,
            args=(remote_sock, client_sock, f"Remote -> Local({client_addr[1]})"),
            daemon=True,
        ).start()
    except Exception as e:
        log_error(f"Tunnel failed: {e}")
        try:
            client_sock.close()
        except OSError:
            pass


def start_playit_bridge(host, port, local_port, plain=False):
    if port == local_port:
        log_error("--port must be the public Playit relay port, not --forward.")
        sys.exit(1)

    ok, probe_result = probe_relay(host, port)
    if not ok:
        log_error(f"Cannot reach Playit relay {host}:{port}: {probe_result}")
        sys.exit(1)
    log_debug(f"Relay reachable at {probe_result}")

    local_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    handler = handle_client_plain if plain else handle_client
    try:
        local_server.bind(("127.0.0.1", local_port))
        local_server.listen(10)
        if plain:
            log_info(f"Playit plain bridge 127.0.0.1:{local_port} -> {host}:{port}")
        else:
            log_info(f"Playit MC-disguised bridge 127.0.0.1:{local_port} -> {host}:{port}")
            log_info(
                f"Traffic: SSH -> XOR -> Login Plugin ({mc_tunnel.TUNNEL_CHANNEL})"
            )
            log_info("playit.gg local target: 127.0.0.1:25565")

        threading.Thread(
            target=_bridge_loop,
            args=(local_server, handler, host, port),
            daemon=True,
        ).start()
        return local_server
    except Exception as e:
        log_error(f"Error starting bridge: {e}")
        sys.exit(1)
