# Sanctuary: Core Technical Reference & Architecture Manual 🌌

This document is the definitive, raw technical specifications manual for Project Sanctuary. It details the exact engineering logic, compilation processes, port mappings, and process lifecycles of the monorepo. 

For the academic threat model, research objectives, and simulation justifications, see **[Sanctuary.md](file:///home/trueking/Safe/Proj/Hug/Sanctuary/docs/Sanctuary.md)**.

---

## 🗺️ System Topology & Data Paths

The monorepo deploys a multi-process gateway routed through **Caddy** as a smart reverse proxy. Caddy terminates public egress traffic on port `7860`, serving a static loading layer during cold boots and proxying private backend channels to local ports.

The system is organized into three layers — Public, Private, and Core. Caddy (`model-routing-engine` on `:7860`/`:7890`) and Gradio (`AI Text Processor` on `:7861`) form the public egress layer. Caddy proxies `/` to Gradio, `/routing-console` to Filebrowser (`:9000`), `/chisel-tunnel` to Chisel (`:6789`), `/gost-bridge` to GOST (`:6790`), `/tensor-mesh` to Sliver C2 (`:11601`), and `/v1` to LiteLLM (`:8080`). KasmVNC (`xorg-ipc-server` on display `:18231`) runs Firefox which renders Caddy's frontend in an automated loop. Supervisord launches `orchestrator.py`, which starts Caddy, Gradio, and VNC.

---

## 🔄 Core operational Logic & Flow

Project Sanctuary operates as a synchronized pipeline spanning three primary stages: **Build/Compilation**, **Deployment/Secret Management**, and **Runtime Orchestration**. Below are the raw, trace-level data paths and execution loops that drive the engine.

### 1. The Secrets Custody Chain (Zero-Trace Evasion)
To prevent administrative keys (`TAILSCALE`, `PLAYIT`, `PASS`) from leaking into public Git logs or remaining visible inside the active system environment memory tree, Sanctuary implements a secure cryptographic chain of custody:

The chain proceeds as follows: the developer (`deploy.py`) decrypts or fetches plain variables, XOR-encrypts them with key `0x5A`, and pushes the XOR-encrypted hex strings to the Hugging Face Secrets API. On boot, Hugging Face injects the encrypted keys into `os.environ`. The orchestrator reads them, hex-decodes and XOR-decrypts them using key `0x5A`, then immediately wipes all secrets from `os.environ` via `os.environ.pop()`. Child subprocesses (Sliver, GOST) receive the decrypted keys directly through stdin or arguments passed in-memory.

### 2. Source-to-Bytecode Compilation & Memory Loading Loop
To bypass platform-level static text and AST scanning tools, readable Python scripts are compiled into bytecode and unlinked:

Raw Python source files pass through `build.py`, which detects `harden('...')` macros. Strings wrapped in `harden()` are base64-encoded and reversed; other strings are left unchanged. A minified intermediate script is written, then compiled to bytecode via `uv run python -m compileall`. The resulting `.pyc` files are promoted out of `__pycache__` to the package root, and the original `.py` source files are deleted via `unlink()`. A thin `orchestrator.py` bootstrap stub is written; at execution, `spec.loader.exec_module()` loads the bytecode directly from memory.

### 3. Runtime Orchestration Lifecycle (Phased Scheduler)
The runtime init loop is managed inside `shared/core/orchestrator.py`, executed under an unprivileged user context. It routes execution through four scheduled boot phases:

Supervisord executes the launcher stub which starts `orchestrator.py`. The runtime proceeds through four phases:

**Phase 0 — Port Binding Gateway:** Caddy starts on `:7860`/`:7890` and immediately serves `loading.html` to satisfy Hugging Face health probes.

**Phase 1 — Cover Workload Spawn:** The Gradio Text Cover App launches on `127.0.0.1:7861`, a dummy 5 GB `pytorch_model.bin` weight file is written, and a background `jitter_task` (numpy dot-product CPU math) begins. Caddy proxies `/` upstream to Gradio once live.

**Phase 2 — Secure Access & Tunnel Spawning:** Secrets are extracted, decrypted, and wiped from `os.environ`. An SSH daemon spawns on `localhost:2222`, Filebrowser starts on port `:9000`, and tunnels are launched (Tailscaled, Chisel, GOST, Ligolo-ng, Sliver C2).

**Phase 3 — Local AI Infrastructure & Visual Debugger:** LiteLLM model router boots on `:8080`, Open WebUI on `:3000`, code-server on `:8888`, and the xorg-ipc-server (`:18231` display) with Fluxbox and Firefox loop initializes.

---

## 🛠️ The Obfuscation, Evasion & Compilation Pipeline


The build engine (`main/scripts/build.py`) performs dynamic code modifications to package the final distribution bundle inside `dist/`.

### 1. Hex-Encoded Reversed-Base64 XOR Obfuscation
String values wrapped inside the `harden("...")` macro at build-time are base64-encoded, reversed, and placed inside double-quotes. At runtime, the strings are decoded on-the-fly via a single-byte public XOR key (`0x5A`).

```python
XOR_KEY = 0x5A

def decode_cmd(encoded_str):
    """Decodes base64-encoded reversed hardened strings."""
    try:
        return base64.b64decode(encoded_str[::-1]).decode()
    except Exception:
        return encoded_str

def unharden_secret(hex_str, key=XOR_KEY):
    """Hex-decodes and XOR-unhardens secret bytes."""
    if not hex_str:
        return ""
    try:
        raw_bytes = bytes.fromhex(hex_str.strip())
        unhardened_bytes = bytes([b ^ key for b in raw_bytes])
        return unhardened_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return hex_str
```

### 2. Bytecode-Only Promotion Mechanics
To prevent standard text-based AST parsers from reading code directly inside the deployed container:
1. The compiler executes `compileall` against all `.py` files inside `dist/` using the target environment's Python version (via `uv`).
2. The generated `.pyc` files are moved out of the `__pycache__/` folder up into the package directory (e.g., `dist/services/foo.pyc`).
3. The original `.py` source files are deleted (`unlinked`).
4. Primary entry-point files (such as `orchestrator.py`) are replaced with a **thin bytecode bootstrap launcher stub** that dynamically hooks into the Python import machinery to load the `.pyc` content straight out of memory:

```python
import importlib.util as _iu,os as _o,sys as _s
_h=_o.path.dirname(_o.path.abspath(__file__))
_n=_o.path.splitext(_o.path.basename(__file__))[0]
_c=_o.path.join(_h,'__pycache__',_n+'.cpython-312.pyc')
if not _o.path.exists(_c):raise FileNotFoundError(f'bytecode for {_n} not found')
_sp=_iu.spec_from_file_location('__main__',_c)
_m=_iu.module_from_spec(_sp)
_m.__file__=_o.path.abspath(__file__)
_s.modules['__main__']=_m
_sp.loader.exec_module(_m)
```

### 3. Camouflage Renames
Binaries are renamed at build time inside the `Dockerfile` to match standard ML process names:

| Original Binary / Tool | Camouflaged Process Name | Role in the Ecosystem |
| :--- | :--- | :--- |
| **Caddy Server** | `/usr/bin/model-routing-engine` | High-performance reverse proxy and routing gateway |
| **Playit-agent** | `/usr/bin/tensor-allocator` | Direct TCP tunnel bridge with Minecraft handshake spoofing |
| **Chisel Proxy** | `/usr/bin/cuda-mesh-bridge` | WebSocket-based HTTP reverse tunnel gateway |
| **GOST Proxy** | `/usr/bin/system-bridge` | Multiplexed Secure SOCKS5/WebSocket tunnel agent |
| **Sliver C2 Server** | `/usr/bin/gradient-optimizer` | Mutual-TLS (mTLS) adversary command-and-control server |
| **Ligolo-ng Proxy** | `/usr/bin/neural-route-controller` | High-speed Layer-3 pivot tunneled network interface |
| **Tailscaled Daemon** | `/usr/bin/python-cache-manager` | Mesh VPN tunnel service daemon |
| **Tailscale CLI** | `/usr/bin/py-cache-cli` | Mesh VPN CLI control panel |
| **Filebrowser** | `/usr/bin/ai-metrics-collector` | Browser-based administrative filesystem interface |
| **KasmVNC Server** | `/usr/bin/display-config` | Headless VNC-over-Websocket X11 display wrapper |
| **Xkasmvnc (X11)** | `/usr/bin/xorg-ipc-server` | Virtual X11 server socket display server |
| **KasmVNC Passwd** | `/usr/bin/digest-generator` | VNC secure credential hashing utility |
| **Fluxbox** | `/usr/bin/layout-decorator` | Low-overhead X11 graphical window manager |
| **Xdpyinfo** | `/usr/bin/adapter-status-checker` | Active graphical frame buffer verification probe |
| **Firefox Browser** | `/opt/render-engine/data-renderer` | Graphical rendering engine for browser-based automation |

### 4. Background Resource Simulation
* **V-Disk Allocation**: Allocates an empty 5GB weight file (`pytorch_model.bin`) inside `/home/user/` to simulate massive model weight buffers on disk.
* **CPU Anomaly Generation**: Spawns a background thread (`jitter_task` inside `shared/services/gradio_service.py`) running numpy matrix multiplication calculations at dynamic, randomized intervals (between 2700 and 5400 seconds) to bypass standard threshold-based alarms.

---

## 📂 Repository File Directory

```
Sanctuary/
├── .env.example                        # Blueprint for local environment variables
├── Makefile                            # Root commands orchestrator (delegates tasks to subfolders)
├── README.md                           # Human landing page and documentation gateway
├── pyproject.toml                      # Monorepo dependencies and Ruff linting configurations
├── uv.lock                             # Lockfile for reproducible environment installations
│
├── docs/                               # Comprehensive technical and justification resources
│   ├── ARCHITECTURAL_GUIDE.md          # [THIS FILE] Core technical manual and port directory
│   ├── CONTEXT.md                      # High-level product security simulation summary
│   ├── RESEARCHER_PROFILE.md           # Professional bios and Academic details
│   └── Sanctuary.md                    # Academic Barlow quote, compliance, and simulation justification
│
├── manifests/                          # Deployment cluster configuration manifests
│   ├── nodes.yaml                      # Space details, target repos, tokens, and service lists
│   └── state.json                      # Automated registry of last built/deployed states
│
├── scripts/                            # Monorepo administration & connection CLI
│   ├── cc.py                           # The Sanctuary client connection manager CLI tool
│   └── deploy.py                       # Code packer, secret obfuscator, and Hugging Face deployer
│
├── main/                               # Subproject holding Space configurations & Docker builds
│   ├── Dockerfile                      # ubuntu-based camouflaged container builder
│   ├── Makefile                        # Compilation, linting, formatting, and cleanup runner
│   ├── sliver                          # Sliver client CLI binary (generated locally)
│   ├── config/                         # Configuration templates injected during container build
│   │   ├── Caddyfile.template          # Reverse proxy mapping layout (substitutes constant ports)
│   │   ├── enabled_services.json       # Set at deploy time to selectively start services
│   │   ├── ligolo-ng.yaml              # Ligolo pivoting specifications
│   │   ├── loading.html                # Boot page returned to satisfy HF container health probes
│   │   └── supervisord.conf            # Daemon supervisor controlling Python bootstrapper
│   │
│   ├── src/                            # Source codes of the Gradio Cover story app
│   │   └── app.py                      # Cover UI (also contains the administrative debug backdoor)
│   │
│   └── scripts/                        # main subproject utility scripts
│       └── build.py                    # Bytecode compiler, obfuscator, minifier, and Docker formatter
│
└── shared/                             # Core libraries shared between nodes and build engines
    ├── core/                           # System orchestration and service registries
    │   ├── __init__.py                 # Core module initialization stub
    │   ├── constants.py                # Canonical port mappings and storage directory paths
    │   ├── orchestrator.py             # Lifecycle daemon driving the multi-phase process boot
    │   ├── service_logs.py             # Multi-sink Loguru logger routing output to separate files
    │   └── service_registry.py         # ALLOWED_SERVICES listing and registry configurations
    │
    └── services/                       # Managed service daemons wrapper classes
        ├── __init__.py                 # Services mapping hooks
        ├── caddy_service.py            # reverse proxy control wrapper
        ├── chisel_service.py           # chisel client/server control wrapper
        ├── code_server_service.py      # VS Code browser server wrapper (runs on port :8888)
        ├── custom_callbacks.py         # Custom LiteLLM request callback statistics logger
        ├── filebrowser_service.py      # Browser-based file manager control wrapper (runs on port :9000)
        ├── gost_service.py             # gost proxy client/server control wrapper
        ├── gradio_service.py           # gradio cover story launcher (runs on port :7861)
        ├── ligolo_service.py           # ligolo pivoting tun controller
        ├── llm_proxy_service.py        # LiteLLM router (OpenAI endpoint on port :8080)
        ├── minecraft_service.py        # Stealth paper server emulator (runs on port :25566)
        ├── open_webui_service.py       # Open WebUI dashboard manager (runs on port :3000)
        ├── playit_service.py           # playit bridge wrapper (tunnels port :2222 through ply.gg)
        ├── sliver_service.py           # sliver command-and-control server control wrapper
        ├── tailscale_service.py        # Userspace tailscaled controller
        └── utils.py                    # XOR decoders, Base64 decoders, and helper routines
```

---

## 🚀 Runtime Process Lifecycle & Boot Sequence

The main system orchestrator (`shared/core/orchestrator.py`) drives a phased boot timeline:

### Phase 0: Port Binding Gateway
Spins up Caddy (`model-routing-engine`) instantly to bind public port `7860` (and secondary `7890`). This ensures platform health checks immediately receive an active HTTP connection serving `static/loading.html` while downstream heavy services compile or load.

### Phase 1: Gradio App Initialization
Launches the **Gradio Cover Story App** (`src/app.py` via `gradio_service.py`) on local port `7861`. Once ready, Caddy proxy bindings seamlessly route incoming traffic directly to it. Pre-allocates the 5GB empty model weights buffer (`pytorch_model.bin`) and boots the background dynamic CPU calculations (`jitter_task`).

### Phase 2: Secret Scrubbing & Tunnel Portal Spawn
* **Secret Scrubbing**: Decrypts environment secret variables (`PASS`, `TAILSCALE`/`A`, `PLAYIT`/`P`) using `unharden_secret()` and stores them in localized memory strings. It then **wipes** all trace variables from the global system process environment (`os.environ`) using `os.environ.pop()` to prevent downstream child process inheritance or dynamic environment scans.
* **Access Portal Spawn**: Initializesuserspace-networking Tailscaled (`python-cache-manager` on SOCKS5 port `:1055`), configures the administrative SSH daemon on port `2222` applying the scrubbed password, initializes Filebrowser (running on port `9000`), and spins up the remaining tunnels (Chisel on `:6789`, GOST on `:6790`, Ligolo-ng proxy on `:11601`, and Sliver C2).

### Phase 3: Localhost Services & Graphical Debugger
* **LiteLLM Router**: Spawns on local port `8080` load-balancing API credentials decrypted from `LLM_KEYS`.
* **OpenWebUI**: Spawns on local port `3000` inside a background worker thread. Delegates all RAG vector embeddings directly to the local LiteLLM proxy and forces client-side STT (Web Speech API) to retain a 0-byte server model footprint.
* **VS Code Server**: Starts `code-server` on local port `8888` without password authentication, relying on userspace-networking tailscale isolation for access.
* **Headless Visualizer**: Spawns KasmVNC (:18231) running a persistent Firefox browser instance in a loop targeting Caddy's routing frontend.

### Subprocess Log Bridging
`shared/core/service_logs.py` handles subprocess logs using a custom pipe-based redirection system:
* Spawns an internal OS pipe (`os.pipe()`) and runs an asynchronous reading thread.
* The thread reads stdout/stderr lines dynamically out of the pipe's read-end using `os.fdopen()`.
* It binds log lines directly into Loguru under unique service keys (e.g., `logger.bind(prefix="TS").info(...)`).
* Depending on `COVERT_LOGGING_MODE`, it routes the data exclusively to individual service log files inside `METRICS_DIR` (Level 1: File-only) or replicates them onto `sys.stdout` with custom color tags (Level 2: Console+File).

---

## 🎛️ Network Routing & Ports Directory

The Sanctuary environment coordinates 14 distinct services, mapped cleanly inside `shared/core/constants.py`:

| Service Identifier | Port | Protocol | Binding Interface | Process Rename / Command |
| :--- | :--- | :--- | :--- | :--- |
| **Caddy Proxy** | `7860` | HTTP | Public (0.0.0.0) | `model-routing-engine run --config {CADDYFILE_PATH}` |
| **Caddy Secondary** | `7890` | HTTP | Public (0.0.0.0) | Used for alternative port mapping / secondary pivots |
| **Gradio Cover App**| `7861` | HTTP | Local (`127.0.0.1`) | `python3 -u /home/user/app.py` |
| **SSH Server** | `2222` | SSH | Local (`127.0.0.1`) | `/usr/sbin/sshd -D` |
| **Chisel Tunnel** | `6789` | WS | Local (`127.0.0.1`) | `cuda-mesh-bridge server --port 6789 --reverse --socks5` |
| **GOST Proxy** | `6790` | MWS | Local (`127.0.0.1`) | `system-bridge -L relay+mws://user:pass@127.0.0.1:6790` |
| **Model Sync** | `6795` | HTTP | Local (`127.0.0.1`) | Internal model replication sync gateway |
| **Sliver C2 Server**| `11601`| mTLS | Local (`127.0.0.1`) | `gradient-optimizer daemon --root-dir {SLIVER_HOME}` |
| **LiteLLM Router** | `8080` | HTTP | Local (`127.0.0.1`) | `/opt/venv-litellm/bin/litellm --config {CONFIG_PATH}` |
| **Filebrowser** | `9000` | HTTP | Local (`127.0.0.1`) | `ai-metrics-collector -p 9000 -d {FILEBROWSER_DB_PATH}` |
| **SOCKS5 Proxy** | `1080` | SOCKS | Local (`127.0.0.1`) | Universal fallback SOCKS5 proxy port |
| **Playit MC Bridge**| `25565`| TCP | Local (`127.0.0.1`) | Playit-gg XOR/Minecraft bridge proxy socket |
| **Minecraft Server**| `25566`| TCP | Local (`127.0.0.1`) | Stealth Paper MC jar (`/tmp/mc/server.jar`) running on JRE 25 |
| **Open WebUI** | `3000` | HTTP | Local (`127.0.0.1`) | `open-webui serve --host 127.0.0.1 --port 3000` |
| **VS Code Server** | `8888` | HTTP | Local (`127.0.0.1`) | `code-server --bind-addr 127.0.0.1:8888 --auth none` |
| **KasmVNC Web Stream**| `8501`| WS | Local (`127.0.0.1`) | Headless graphics streaming port (KasmVNC display `:18231`) |

> [!WARNING]
> **Filebrowser Port Mapping Mismatch**: Although `shared/core/constants.py` references port `6801` under the key `"filebrowser"`, the underlying wrapper `filebrowser_service.py` executes Filebrowser on port `9000` (`-p 9000`). Caddy handles this mismatch inside the Caddyfile template by proxying `/routing-console*` requests directly to port `6801` (which is standard for constants-mapping compatibility) or mapping routes appropriately depending on active variables. Ensure that Caddy mapping coordinates reflect `9000` when updating the network interface parameters.

### 1. Caddy Router Configurations (`Caddyfile.template`)
```caddy
# Bind to Hugging Face Spaces public ports
:7860, :7890 {
    # Serve loading page during boots or service failure
    handle_errors {
        root * {STATIC_DIR}
        rewrite * /loading.html
        file_server
    }

    # Static Assets (Bypasses Python runtime completely)
    handle /static/* {
        root * {STATIC_DIR}
        file_server
    }

    # Secure Websocket Tunnels and Pivoting Interfaces
    handle_path /chisel-tunnel* { reverse_proxy 127.0.0.1:6789 }
    handle /gost-bridge*       { reverse_proxy 127.0.0.1:6790 }
    handle /tensor-mesh*        { 
        reverse_proxy https://127.0.0.1:11601 {
            transport http { tls_insecure_skip_verify }
        }
    }

    # LiteLLM proxy and OpenAI endpoint routing
    handle /v1*                 { reverse_proxy 127.0.0.1:8080 }
    handle /health*             { reverse_proxy 127.0.0.1:8080 }

    # Filebrowser Dashboard Console
    handle /routing-console*    { reverse_proxy 127.0.0.1:6801 }

    # Default Fallback to Gradio Cover App
    handle {
        reverse_proxy 127.0.0.1:7861 {
            header_up X-Forwarded-Proto https
        }
    }
}
```

### 2. Tunnel Technologies
* **Chisel (`cuda-mesh-bridge`)**: Establishes a raw TCP-over-WebSocket tunnel listening locally on port `6789`.
* **GOST (`system-bridge`)**: Multiplexed proxy mapping SOCKS5 over Secure WebSockets on port `6790`.
* **Tailscale (`python-cache-manager`)**: Mesh VPN executed inside userspace-networking mode (`--tun=userspace-networking`) mapping an internal SOCKS5 interface to port `1055` and a control socket to `.torch_metrics/tailscaled.sock`.
* **Ligolo-ng (`neural-route-controller`)**: Pivot controller establishing high-performance virtual TUN interfaces (`sudo -n /usr/bin/neural-route-controller -laddr 127.0.0.1:11601 -selfcert -selfcert-domain ligolo`).
* **Playit-gg (`tensor-allocator`)**: Direct TCP tunnel utilizing custom XOR obfuscation and Minecraft handshake patterns. Establishes a local bridge (`playit_service.py`) on port `25565` using Playit's CLI daemon.

---

## 📺 Headless Graphical Remote Debugger

* **X11 display**: Headless graphics are handled by a virtual frame buffer via KasmVNC's custom server (`/usr/bin/xorg-ipc-server`) bound to display port `:18231`.
* **Config Hardening**: WebRTC and external STUN servers are programmatically **disabled** inside `~/.vnc/kasmvnc.yaml` to prevent outbound UDP leaks.
* **Credentials Pre-seeding**: Executes `digest-generator` (kasmvncpasswd) in a subprocess, feeding raw VNC credentials (`kasmpass`) into storage, bypassing interactive configurations.
* **Window Dresser**: Spawns Fluxbox (`layout-decorator`) in display `:18231` using `~/.vnc/xstartup` to manage unprivileged visual canvas frames.
* **Browser Automation Loop**: Firefox (`data-renderer`) launches inside display `:18231` targeting Caddy's frontend `http://127.0.0.1:7860` in a persistent rendering loop.

---

## 🚪 Gradio Control Panel Backdoor

The main Gradio interface text box parses command variables directly inside `main/src/app.py`:

* `SHOW_ALL_LOGS`: Aggregates and dumps logs from all running system services under `~/.torch_metrics/*.log`.
* `SHOW_API_STATS`: Summarizes local LiteLLM API proxy requests and usage counts parsed out of `~/.torch_metrics/api_calls.txt`.
* `SHOW_LOGS_MC`: Dumps active logs from the stealth Paper Minecraft server (`/tmp/mc/logs/latest.log`).
* `SHOW_LOGS_<SERVICE>`: Directly streams logging channels from individual background daemons (e.g. Sliver, Ligolo, Tailscale, etc.).

---

## 📖 Developer Playbook: How-to Guides

### 1. How to Add a New Camouflaged Service
1. **Register Service name**: Add identifier string to `shared/core/service_registry.py` inside `ALLOWED_SERVICES`.
2. **Define Port and Directories**: Add port configurations to `PORTS` inside `shared/core/constants.py`.
3. **Create Module**: Build `shared/services/my_service.py` wrapping subprocess calls.
4. **Hook Orchestrator**: Update `shared/core/orchestrator.py` to import and call the service.
5. **Bridge Logs**: Add a dedicated Subprocess Bridge handle in `shared/core/service_logs.py`.

### 2. How to Provision and Deploy a Node
1. **Manifest Configuration**: Append node definitions to `manifests/nodes.yaml`.
2. **Set Environment Keys**: Set write credentials in shell variables (`HF_DEPLOY_TOKEN`, `TAILSCALE`, `PLAYIT`, `PASS`).
3. **Run Packing Pipeline**:
   ```bash
   make deploy LOGS=2 HARDENER=bytecode
   ```

### 3. How to Operate Tunnels via the Client CLI (`cc.py`)
* **Chisel Tunnel with interactive SSH session**:
  ```bash
  uv run python scripts/cc.py chisel --node server-01 -s
  ```
* **GOST Proxy SOCKS5 (Port 1080)**:
  ```bash
  uv run python scripts/cc.py gost --node server-01 -p
  ```
* **Arbitrary Local Port Forwarding**:
  ```bash
  uv run python scripts/cc.py chisel --node server-01 -L 6801:127.0.0.1:9000
  ```
* **Minecraft / Playit bridge connections**:
  ```bash
  uv run python scripts/cc.py playit --host south-forests.gl.at.ply.gg --port 25565 -s
  ```
* **Query node status and stream logs**:
  ```bash
  uv run python scripts/cc.py node server-01 --status
  uv run python scripts/cc.py node server-01 --logs --follow
  ```
