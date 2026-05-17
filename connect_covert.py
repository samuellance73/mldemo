import sys
import socket
import threading

XOR_KEY = 0x5A # Must match the key on the server (wrapper.py)
LOCAL_PORT = 2222

def pipe_xor(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            # XOR every byte in transit to scramble/unscramble it
            scrambled = bytes([b ^ XOR_KEY for b in data])
            dst.sendall(scrambled)
    except Exception:
        pass
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
    # Prefix with total packet length
    return pack_varint(len(data)) + data

def start_local_bridge(remote_host, remote_port):
    local_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        local_server.bind(("127.0.0.1", LOCAL_PORT))
        local_server.listen(5)
        print(f"[*] Stealth XOR bridge listening locally on 127.0.0.1:{LOCAL_PORT}")
        print(f"[*] Forwarding obfuscated traffic to {remote_host}:{remote_port}")
        print(f"[*] To connect, run this in another terminal: ssh user@127.0.0.1 -p {LOCAL_PORT}")
        
        while True:
            client_sock, addr = local_server.accept()
            try:
                # Connect to Playit's public address
                remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote_sock.connect((remote_host, remote_port))
                
                # FAKE GAME HEADER: Send dynamic Minecraft Handshake matching the exact Playit domain
                mc_handshake = build_mc_handshake(remote_host, remote_port)
                remote_sock.sendall(mc_handshake)
                
                # Spawn bidirectional pipes
                threading.Thread(target=pipe_xor, args=(client_sock, remote_sock), daemon=True).start()
                threading.Thread(target=pipe_xor, args=(remote_sock, client_sock), daemon=True).start()
            except Exception as e:
                print(f"[-] Failed to establish connection to remote tunnel: {e}")
                try: client_sock.close()
                except: pass
    except Exception as e:
        print(f"[-] Error starting local bridge: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 connect_covert.py <playit_host> <playit_port>")
        print("Example: python3 connect_covert.py south-forests.gl.at.ply.gg 43345")
        sys.exit(1)
        
    host = sys.argv[1]
    port = int(sys.argv[2])
    start_local_bridge(host, port)
