import base64

XOR_KEY = 0x5A


def decode_cmd(encoded_str):
    """Decodes base64-encoded obfuscated strings."""
    return base64.b64decode(encoded_str[::-1]).decode()


def deobfuscate_secret(hex_str, key=XOR_KEY):
    """Decrypts XOR-obfuscated secrets with standard print verification."""
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
