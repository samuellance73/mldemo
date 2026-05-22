"""Canonical service names for per-node manifests and runtime gating."""

ALLOWED_SERVICES = frozenset(
    {
        "nginx",
        "filebrowser",
        "tailscale",
        "playit",
        "chisel",
        "gost",
        "sliver",
        "minecraft",
    }
)

ENABLED_SERVICES_PATH = "/home/user/config/enabled_services.json"
