"""Bridge to server-side src/services/utils.py (canonical XOR_KEY and secret helpers)."""

import importlib.util
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UTILS_PATH = os.path.join(_REPO_ROOT, "src", "services", "utils.py")

_spec = importlib.util.spec_from_file_location("ml_services_utils", _UTILS_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

XOR_KEY = _mod.XOR_KEY
decode_cmd = _mod.decode_cmd
deobfuscate_secret = _mod.deobfuscate_secret
