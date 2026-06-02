"""
Minecraft 1.20.2 (protocol 763) login-phase framing for SSH tunnel disguise.
Payload is XOR-scrambled (see utils.XOR_KEY) inside Login Plugin messages on channel bungeecord:main.
"""

import struct
import threading
import uuid

from sanctuary.common.utils import XOR_KEY

PROTOCOL_VERSION = 763
TUNNEL_CHANNEL = "bungeecord:main"
MC_SERVER_PORT = 25566
TUNNEL_DEFAULT_PORT = 2222

PKT_HANDSHAKE = 0x00
HANDSHAKE_STATE_STATUS = 1
HANDSHAKE_STATE_LOGIN = 2
PKT_LOGIN_SUCCESS = 0x02
PKT_LOGIN_PLUGIN_REQUEST = 0x03
PKT_LOGIN_PLUGIN_RESPONSE = 0x04
PKT_LOGIN_START = 0x00


def pack_varint(val):
    out = b""
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out += bytes([byte | 0x80])
        else:
            out += bytes([byte])
            break
    return out


def read_varint_from_buf(buf, offset=0):
    val = 0
    shift = 0
    pos = offset
    while pos < len(buf):
        byte = buf[pos]
        pos += 1
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return val, pos
        shift += 7
        if shift > 35:
            raise ValueError("varint too long")
    raise ValueError("incomplete varint")


def pack_string(s):
    b = s.encode("utf-8")
    return pack_varint(len(b)) + b


def read_string_from_payload(payload, offset=0):
    length, pos = read_varint_from_buf(payload, offset)
    end = pos + length
    if end > len(payload):
        raise ValueError("short string in packet")
    return payload[pos:end].decode("utf-8", errors="replace"), end


def pack_bytes(data):
    return pack_varint(len(data)) + data


def xor_bytes(data):
    return bytes([b ^ XOR_KEY for b in data])


def frame_packet(packet_id, payload):
    body = pack_varint(packet_id) + payload
    return pack_varint(len(body)) + body


def build_handshake(host, port, next_state=2):
    host_bytes = host.encode("utf-8")
    payload = (
        pack_varint(PROTOCOL_VERSION)
        + pack_varint(len(host_bytes))
        + host_bytes
        + struct.pack(">H", port)
        + pack_varint(next_state)
    )
    return frame_packet(PKT_HANDSHAKE, payload)


def build_login_start(username="Steve"):
    payload = pack_string(username) + b"\x00"
    return frame_packet(PKT_LOGIN_START, payload)


def build_login_success(username="Steve"):
    payload = uuid.uuid4().bytes + pack_string(username) + pack_varint(0)
    return frame_packet(PKT_LOGIN_SUCCESS, payload)


def frame_login_plugin_response(message_id, data=b""):
    payload = pack_varint(message_id) + b"\x01" + pack_bytes(data)
    return frame_packet(PKT_LOGIN_PLUGIN_RESPONSE, payload)


def frame_login_plugin_request(message_id, data):
    payload = pack_varint(message_id) + pack_string(TUNNEL_CHANNEL) + pack_bytes(data)
    return frame_packet(PKT_LOGIN_PLUGIN_REQUEST, payload)


def wrap_tunnel_client(xor_payload):
    return frame_login_plugin_response(0, xor_payload)


class PacketReader:
    def __init__(self, sock):
        self.sock = sock
        self._buf = b""
        self.consumed = b""

    def _fill(self):
        chunk = self.sock.recv(8192)
        if not chunk:
            raise ConnectionError("peer closed")
        self._buf += chunk

    def read_packet(self):
        while True:
            try:
                pkt_len, pos = read_varint_from_buf(self._buf)
            except ValueError:
                self._fill()
                continue
            total = pos + pkt_len
            while len(self._buf) < total:
                self._fill()
            frame = self._buf[:total]
            self.consumed += frame
            packet = self._buf[pos:total]
            self._buf = self._buf[total:]
            pkt_id, ppos = read_varint_from_buf(packet, 0)
            return pkt_id, packet[ppos:]


def extract_tunnel_from_response(payload):
    _, pos = read_varint_from_buf(payload, 0)
    if pos >= len(payload) or payload[pos] == 0:
        return None
    pos += 1
    length, pos = read_varint_from_buf(payload, pos)
    end = pos + length
    if end > len(payload):
        return None
    return xor_bytes(payload[pos:end])


def extract_tunnel_from_request(payload):
    msg_id, pos = read_varint_from_buf(payload, 0)
    channel, pos = read_string_from_payload(payload, pos)
    if channel != TUNNEL_CHANNEL:
        return None, msg_id
    length, pos = read_varint_from_buf(payload, pos)
    end = pos + length
    if end > len(payload):
        return None, msg_id
    return xor_bytes(payload[pos:end]), msg_id


def client_login(remote_sock, host, port, remote_target_port=2222, timeout=10.0):
    remote_sock.settimeout(timeout)
    remote_sock.sendall(build_handshake(host, port))
    username = f"Steve_{remote_target_port}"
    remote_sock.sendall(build_login_start(username))
    reader = PacketReader(remote_sock)
    while True:
        pkt_id, payload = reader.read_packet()
        if pkt_id == PKT_LOGIN_SUCCESS:
            break
        if pkt_id == PKT_LOGIN_PLUGIN_REQUEST:
            mid, _ = read_varint_from_buf(payload, 0)
            remote_sock.sendall(frame_login_plugin_response(mid, b""))
    remote_sock.settimeout(None)
    return reader


def _skip_proxy_header(reader):
    """If the buffer starts with 'PROXY ' (HAProxy PROXY protocol v1), consume and discard it."""
    # Peek: fill at least 6 bytes
    while len(reader._buf) < 6:
        reader._fill()
    if reader._buf[:6] == b"PROXY ":
        # Read until CRLF
        while b"\r\n" not in reader._buf:
            reader._fill()
        end = reader._buf.index(b"\r\n") + 2
        header = reader._buf[:end]
        reader.consumed += header
        reader._buf = reader._buf[end:]
        return header.decode(errors="replace").strip()
    return None


def is_tunnel_username(username):
    return username == "Steve" or username.startswith("Steve_")


def tunnel_target_port(username):
    if not username.startswith("Steve_"):
        return TUNNEL_DEFAULT_PORT
    try:
        return int(username.split("_")[-1])
    except ValueError:
        return TUNNEL_DEFAULT_PORT


def parse_handshake_next_state(payload):
    pos = 0
    _, pos = read_varint_from_buf(payload, pos)
    _, pos = read_string_from_payload(payload, pos)
    if pos + 2 > len(payload):
        raise ValueError("short handshake")
    pos += 2
    next_state, _ = read_varint_from_buf(payload, pos)
    return next_state


def server_dispatch(client_sock, timeout=10.0):
    """Classify inbound connection: status ping, SSH tunnel login, or real MC login."""
    client_sock.settimeout(timeout)
    reader = PacketReader(client_sock)
    proxy_header = _skip_proxy_header(reader)
    if proxy_header:
        import sys

        print(
            f"[mc_tunnel] skipped PROXY header: {proxy_header}",
            file=sys.stderr,
            flush=True,
        )
    pkt_id, payload = reader.read_packet()
    if pkt_id != PKT_HANDSHAKE:
        raise ValueError(f"expected handshake, got {pkt_id:#x}")

    if parse_handshake_next_state(payload) == HANDSHAKE_STATE_STATUS:
        client_sock.settimeout(None)
        return "status", reader, MC_SERVER_PORT

    pkt_id, payload = reader.read_packet()
    if pkt_id != PKT_LOGIN_START:
        raise ValueError(f"expected login start, got {pkt_id:#x}")

    username = "Steve"
    try:
        username, _ = read_string_from_payload(payload, 0)
    except Exception:
        pass

    client_sock.settimeout(None)
    if is_tunnel_username(username):
        target_port = tunnel_target_port(username)
        client_sock.sendall(build_login_success())
        return "tunnel", reader, target_port

    return "mc", reader, MC_SERVER_PORT


def server_consume_login(client_sock, timeout=10.0):
    """Backward-compatible wrapper returning (is_tunnel, reader, target_port)."""
    mode, reader, target_port = server_dispatch(client_sock, timeout)
    if mode == "status":
        return False, reader, target_port
    return mode == "tunnel", reader, target_port


def _pump_socket(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)
    except (OSError, ConnectionError):
        pass


def relay_passthrough(reader, backend_sock, client_sock):
    """Replay captured login bytes to a real MC server, then plain TCP relay."""
    pending = reader.consumed + reader._buf
    reader._buf = b""
    if pending:
        backend_sock.sendall(pending)
    threading.Thread(
        target=_pump_socket, args=(client_sock, backend_sock), daemon=True
    ).start()
    try:
        _pump_socket(backend_sock, client_sock)
    finally:
        for s in (client_sock, backend_sock):
            try:
                s.close()
            except OSError:
                pass


def _pump_plain_to_mc(src, mc_sock, wrap_fn):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            mc_sock.sendall(wrap_fn(xor_bytes(data)))
    except (OSError, ConnectionError):
        pass
    finally:
        try:
            src.close()
        except OSError:
            pass


def relay_client(mc_reader, local_sock, mc_sock):
    """After client_login: frame local SSH <-> remote MC socket."""
    threading.Thread(
        target=_pump_plain_to_mc,
        args=(local_sock, mc_sock, wrap_tunnel_client),
        daemon=True,
    ).start()
    try:
        out_mid = 0
        while True:
            pkt_id, payload = mc_reader.read_packet()
            if pkt_id == PKT_LOGIN_PLUGIN_REQUEST:
                chunk, mid = extract_tunnel_from_request(payload)
                if chunk:
                    local_sock.sendall(chunk)
                if mid is not None:
                    mc_sock.sendall(frame_login_plugin_response(mid, b""))
            elif pkt_id == PKT_LOGIN_PLUGIN_RESPONSE:
                chunk = extract_tunnel_from_response(payload)
                if chunk:
                    local_sock.sendall(chunk)
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        for s in (local_sock, mc_sock):
            try:
                s.close()
            except OSError:
                pass


def relay_server(mc_reader, ssh_sock, mc_sock):
    """After server_consume_login: frame ssh <-> playit client socket."""
    out_mid = 0

    def wrap_out(data):
        nonlocal out_mid
        out_mid += 1
        return frame_login_plugin_request(out_mid, data)

    threading.Thread(
        target=_pump_plain_to_mc,
        args=(ssh_sock, mc_sock, wrap_out),
        daemon=True,
    ).start()
    try:
        while True:
            pkt_id, payload = mc_reader.read_packet()
            if pkt_id == PKT_LOGIN_PLUGIN_RESPONSE:
                chunk = extract_tunnel_from_response(payload)
                if chunk:
                    ssh_sock.sendall(chunk)
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        for s in (ssh_sock, mc_sock):
            try:
                s.close()
            except OSError:
                pass
