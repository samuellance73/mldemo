"""Canonical service names for per-node manifests and runtime gating."""

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
    }
)

ENABLED_SERVICES_PATH = "/home/user/config/enabled_services.json"
