import re
import base64

def encode_cmd(decoded_str):
    return base64.b64encode(decoded_str.encode()).decode()[::-1]

def _process_service_py(content):
    def replacer(match):
        raw_cmd = match.group(1)
        encoded = encode_cmd(raw_cmd)
        return f'"{encoded}"'
    return re.sub(r'harden\(\s*"([^"]+)"\s*\)', replacer, content)

src = r'''
payload_cfg = decode_cmd(harden("network:\n  interface: 127.0.0.1\n  websocket_port: 28931\n"))
b_wm = decode_cmd(harden("fluxbox"))
'''
print("Original:")
print(src)
print("Processed:")
print(_process_service_py(src))
