# Project Context

## Overview
This project is an advanced, multi-service application environment designed for deployment within Hugging Face Spaces. While presenting an intuitive Gradio AI Text Processor interface to users, it encapsulates a robust background networking and management stack (including Nginx, Tailscale, Filebrowser, Playit, Chisel, GOST, and Minecraft) to ensure high availability and resilient remote administration.

---

## Repository Layout

```
├── Dockerfile
├── README.md
├── Makefile
├── config/
│   └── nginx.conf.template
├── docs/
│   ├── CONTEXT.md
│   └── SANCTUARY.md
├── manifests/
│   ├── nodes.yaml
│   └── state.json
├── scripts/
│   ├── build.py
│   ├── cc.py
│   ├── deploy.py
│   └── cc_utils/
│       ├── __init__.py
│       ├── chisel.py
│       ├── common.py
│       └── playit.py
├── src/
│   ├── app.py
│   ├── README.md
│   ├── core/
│   │   └── orchestrator.py
│   └── services/
│       ├── __init__.py
│       ├── utils.py
│       ├── nginx.py
│       ├── tailscale.py
│       ├── playit.py
│       ├── chisel.py
│       ├── filebrowser.py
│       ├── minecraft.py
│       └── gost.py
└── dist/       # (Generated production build)
```

---

## Build Pipeline (`scripts/build.py`)

Run `make build LOGS=1` (default) from the repo root to log to standard files. Use `make build LOGS=2` to output logs to both console and files simultaneously. Use `make build LOGS=0` for a streamlined production build with minimal logging overhead. The pipeline performs the following transformations:

1. **`src/core/orchestrator.py`** → `dist/core/orchestrator.py`
   - Encodes internal shell commands for clean packaging
   - Minifies code via `python-minifier` to remove comments, docstrings, and unneeded whitespace

2. **`Dockerfile`** → `dist/Dockerfile`
   - Encodes external download URLs dynamically
   - Strips all `#` comment lines for minimal footprint

3. **`src/app.py`** → `dist/app.py`
   - Minifies code via `python-minifier` to remove comments, docstrings, and unneeded whitespace

4. **`src/services/`** → `dist/services/`
   - Iterates through all Python modules under `src/services/`
   - Resolves and replaces internal shell command obfuscation `OBFUSCATE(...)`
   - Minifies code via `python-minifier` to remove comments, docstrings, and unneeded whitespace

5. **`src/README.md`** & **`.gitattributes`** → `dist/`
   - Copied verbatim for Space configuration and documentation

After running `scripts/build.py`, the `dist/` directory is fully prepared for cloud deployment.

---

## Tunneling and Connectivity Client (`scripts/cc.py`)

A protocol-focused CLI tool designed to establish local endpoints for interacting with the background services running in the Hugging Face Space nodes. It implements three main connection modes:

1. **Playit mode (`playit`)**:
   - Establishes a local bridge forwarding to the remote Playit public tunnel address.
   - Performs a Minecraft Handshake to masquerade traffic as game network packets.
   - Applies bidirectional XOR-obfuscation (`0x5A`) to stream standard SSH traffic cleanly.
   - Usage: `uv run python scripts/cc.py playit --host <host> --port <port> [--local-port 2222]`

2. **Chisel mode (`chisel`)**:
   - Connects directly to the node's WebSocket/HTTP proxy endpoint (using `state.json` to resolve the node name to the target Hugging Face space URL).
   - Establishes remote tunnels mapping:
     - Local SOCKS5 Proxy: `1080`
     - SSH Forwarding: `2222 -> 127.0.0.1:2222`
     - Filebrowser Forwarding: `9000 -> 127.0.0.1:9000`
   - Usage: `uv run python scripts/cc.py chisel --node <node-name> [--auth user:apple123]`

3. **GOST mode (`gost`)**:
   - Connects directly to the node's multiplexed WebSocket proxy endpoint (routed via `/gost-bridge`).
   - Resolves the target Hugging Face Space URL, appending `:443` and forcing route matching using `?path=/gost-bridge` parameters on the secure WebSocket scheme `relay+mwss://`.
   - Supports two proxy modes:
     - Local SOCKS5 Proxy: `1080` (Usage: `--proxy-mode socks5`)
     - SSH Forwarding: `2222 -> 127.0.0.1:2222` (Usage: `--proxy-mode ssh`)
   - Usage: `uv run python scripts/cc.py gost --node <node-name> [--auth user:apple123] [--proxy-mode socks5|ssh]`

---

## Runtime Stack (inside the container)

To seamlessly blend with standard machine learning container runtimes, core management utilities are mapped to AI-domain naming conventions:

| Encapsulated Service Name   | Core Utility      | Operational Purpose            |
|-----------------------------|-------------------|--------------------------------|
| `python-cache-manager`      | `tailscaled`      | Secure mesh network daemon     |
| `py-cache-cli`              | `tailscale`       | Mesh network control CLI       |
| `ai-metrics-collector`      | `filebrowser`     | Web-based file manager         |
| `tensor-allocator`          | `playit-agent`    | Public tunnel connector        |
| `cuda-mesh-bridge`          | `chisel`          | High-speed WebSocket proxy     |
| `system-bridge`             | `gost`            | Multiplexed WebSocket proxy    |

Telemetry and service logs are securely archived in `/home/user/.torch_metrics/`:
| Log File          | Monitored Service Contents        |
|-------------------|-----------------------------------|
| `ts_daemon.log`   | Tailscale initialization output   |
| `fb.log`          | Filebrowser access and errors     |
| `tm_daemon.log`   | Playit connection status          |
| `chisel.log`      | Chisel proxy connection events    |
| `gost.log`        | GOST tunnel proxy events          |
| `nginx.log`       | Nginx service and access events   |
| `mc_daemon.log`   | Minecraft startup and logs        |
| `startup.log`     | Master orchestrator boot record   |

---

## Diagnostic Console Commands (via Gradio UI)

Administrators can input specific diagnostic keys into the Gradio text input box to retrieve system telemetry:

| Command Key              | Output Returned                 |
|--------------------------|---------------------------------|
| `SHOW_LOGS_TAILSCALE`    | Contents of `ts_daemon.log`     |
| `SHOW_LOGS_FILEBROWSER`  | Contents of `fb.log`            |
| `SHOW_LOGS_METRICS2`     | Contents of `tm_daemon.log`     |
| `SHOW_LOGS_CHISEL`       | Contents of `chisel.log`        |
| `SHOW_LOGS_GOST`         | Contents of `gost.log`          |
| `SHOW_LOGS_NGINX`        | Contents of `nginx.log`         |
| `SHOW_LOGS_NGINX_ACCESS` | Contents of Nginx `/tmp/access.log` |
| `SHOW_LOGS_NGINX_ERROR`  | Contents of Nginx `/tmp/error.log`  |
| `SHOW_LOGS_MC`           | Contents of `mc_daemon.log`     |
| `SHOW_ALL_LOGS`          | Complete service log summary    |
| `SHOW_LOGS_STARTUP`      | Master startup log verification |

---

## Secure Environment Configuration (HF Space Secrets)

To protect sensitive credentials during container initialization, high-value tokens are securely passed using XOR encryption and stored in single environment variables:

| Environment Key | Configured Purpose                                             |
|-----------------|----------------------------------------------------------------|
| `A`             | Tailscale network authentication key (XOR hex encoded)         |
| `P`             | Playit tunnel secret credential (XOR hex encoded)              |
| `C`             | Chisel secure WebSocket credentials (XOR hex encoded)          |
| `PASS`          | SSH user password (XOR hex encoded)                            |

All secret variables are actively purged from the process environment memory immediately after service initialization.

### Local Secret Resolution (.env)

During local deployment, `scripts/deploy.py` resolves secrets standardizing to node-specific or global variables, obfuscates them, and pushes them to Hugging Face:

- **Tailscale Key**: Resolved from `TAILSCALE_<suffix>` (e.g. `TAILSCALE_01` for node `server-01`) or global `TAILSCALE` / legacy `A`.
- **Playit Secret**: Resolved from `PLAYIT_<suffix>` (e.g. `PLAYIT_01` for node `server-01`) or global `PLAYIT` / legacy `P`.
- **Chisel Auth**: Resolved from `CHISEL_<suffix>` or global `CHISEL` / legacy `C`.
- **SSH Password**: Resolved from `SSH_<suffix>` or global `SSH` / legacy `PASS`.

---

## Key Architectural Guidelines

- **Source Control**: All edits must be made within `src/` or `config/`. The `dist/` directory is automatically regenerated during `make build`.
- **Command Obfuscation**: Use `OBFUSCATE("...")` in `src/core/orchestrator.py` and `src/services/` modules, and `URL_OBFUSCATE("...")` in `Dockerfile` to maintain clean encapsulation.
- **Nginx Route Mapping**: The `try_files` configuration explicitly matches `/index.html @backend;` to route traffic seamlessly to Gradio, preventing directory listing 403 Forbidden checks.
- **Minecraft Tmux Session**: The Minecraft stealth daemon executes within a background tmux session named `mc_server` to facilitate easy interactive administration (e.g., `ssh -t -p 2222 user@127.0.0.1 "tmux attach -t mc_server"`).
- **Efficient Heartbeat**: Standard `numpy` operations provide background active heartbeat and load simulation without requiring heavy dependencies.
- **Resource Optimization**: PyTorch libraries are intentionally omitted to maximize available storage and speed (~700 MB savings).
- **Service Integration**: The internal SSH daemon operates on port 25565, enabling seamless tunneling over standard game routing ports.

Chisel command:  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@127.0.0.1 -p 2222