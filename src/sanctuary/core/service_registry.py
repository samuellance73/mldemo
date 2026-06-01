"""Canonical service names for per-node manifests and runtime gating."""

from pathlib import Path

ALLOWED_SERVICES = frozenset(
    {
        "caddy",
        "filebrowser",
        "tailscale",
        "playit",
        "chisel",
        "gost",
        "ligolo",
        "sliver",
        "minecraft",
        "test",
        "llm_proxy",
        "open_webui",
        "code_server",
        "visual_debugger",
        "gradio",
    }
)

ENABLED_SERVICES_PATH = str(Path.home() / "config" / "enabled_services.json")
