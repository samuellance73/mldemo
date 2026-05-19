import os
import json
import sys

XOR_KEY = 0x5A
DEBUG_MODE = False

def log_debug(msg):
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}", flush=True)

def log_error(msg):
    print(f"[-] {msg}", file=sys.stderr, flush=True)

def log_info(msg):
    print(f"[+] {msg}", flush=True)

def pipe_xor(src, dst, label="pipe"):
    try:
        log_debug(f"{label}: Started transfer.")
        total_bytes = 0
        while True:
            data = src.recv(8192)
            if not data:
                log_debug(f"{label}: Connection closed by sender (EOF).")
                break
            total_bytes += len(data)
            scrambled = bytes([b ^ XOR_KEY for b in data])
            dst.sendall(scrambled)
        log_debug(f"{label}: Finished transfer. Total bytes: {total_bytes}")
    except Exception as e:
        log_debug(f"{label}: Connection error: {e}")
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def pack_varint(val):
    out = b''
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out += bytes([byte | 0x80])
        else:
            out += bytes([byte])
            break
    return out

def build_mc_handshake(host, port):
    host_bytes = host.encode('utf-8')
    # Packet ID (0x00) + Protocol (763) + Host Len + Host + Port (2 bytes) + Next State (2 for Login)
    data = pack_varint(0) + pack_varint(763) + pack_varint(len(host_bytes)) + host_bytes + port.to_bytes(2, 'big') + pack_varint(2)
    return pack_varint(len(data)) + data

def get_node_url(node_name):
    # Locate state.json relative to the repository root
    # cc_utils is nested in scripts/
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    state_path = os.path.join(repo_root, "manifests", "state.json")
    if not os.path.exists(state_path):
        raise FileNotFoundError(f"State file '{state_path}' not found. Build/deploy first.")
    
    with open(state_path, "r") as f:
        state = json.load(f)
    
    node_info = state.get(node_name)
    if not node_info:
        raise ValueError(f"Node '{node_name}' not found. Available: {', '.join(state.keys())}")
        
    url = node_info.get("url")
    if not url:
        raise ValueError(f"Node '{node_name}' has no URL configured.")
    return url
