import base64

def decode_cmd(encoded_str):
    return base64.b64decode(encoded_str[::-1]).decode()
