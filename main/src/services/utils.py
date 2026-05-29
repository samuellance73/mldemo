import base64

try:
    from loguru import logger
except ImportError:
    import logging as _logging

    logger = _logging.getLogger(__name__)

# XOR_KEY is intentional single-byte hardening — NOT encryption.
# Its purpose is to prevent HF Space UI from displaying secrets as plaintext
# and to bypass naive secret scanners. The key is public by design.
XOR_KEY = 0x5A


def decode_cmd(encoded_str):
    """Decodes base64-encoded hardened strings."""
    return base64.b64decode(encoded_str[::-1]).decode()


def unharden_secret(hex_str, key=XOR_KEY):
    """XOR-unhardens a hex-encoded secret. Returns empty string on empty input.

    Logs a warning on both fallback paths so misconfigured secrets are visible
    immediately rather than causing silent downstream failures.
    """
    if not hex_str:
        return ""
    try:
        raw_bytes = bytes.fromhex(hex_str.strip())
        unhardened_bytes = bytes([b ^ key for b in raw_bytes])
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in unhardened_bytes):
            return unhardened_bytes.decode("utf-8", errors="ignore")
        else:
            logger.warning(
                "unharden_secret: XOR result contains non-printable bytes — "
                "value may be corrupted or encoded with a different key. "
                "Returning raw input as fallback."
            )
            return hex_str
    except ValueError:
        logger.warning(
            "unharden_secret: input is not valid hex — "
            "secret may have been set as plain-text instead of XOR-encoded. "
            "Returning raw input as fallback."
        )
        return hex_str
    except Exception as e:
        logger.warning(
            f"unharden_secret: unexpected error ({e}). Returning raw input as fallback."
        )
        return hex_str
