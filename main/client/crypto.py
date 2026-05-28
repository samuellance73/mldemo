"""Bridge to server-side src/services/utils.py (canonical XOR_KEY and secret helpers)."""

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UTILS_PATH = _REPO_ROOT / "src" / "services" / "utils.py"

_spec = importlib.util.spec_from_file_location("ml_services_utils", str(_UTILS_PATH))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

XOR_KEY = _mod.XOR_KEY
decode_cmd = _mod.decode_cmd
deobfuscate_secret = _mod.deobfuscate_secret
