# Sanctuary: The Definitive Security Simulation Engine & Architecture Masterguide 🌌

> *"We are creating a world that all may enter without privilege or prejudice accorded by race, economic power, military force, or station of birth... a world where anyone, anywhere may express his or her beliefs, no matter how singular, without fear of being coerced into silence or conformity."*
> — John Perry Barlow, *A Declaration of the Independence of Cyberspace* (1996)

---

## 📖 Executive Summary & Mission Objective

**Project Sanctuary** is an authorized, multi-node security evaluation target modeled by the **Hugging Face Product Security** team. It is designed to run within isolated Hugging Face Spaces to test platform boundaries, egress telemetry, host intrusion detection systems (HIDS), process monitoring engines, and static file analysis scanners under realistic, behaviorally masked post-compromise conditions.

To achieve authentic, high-fidelity security research, the environment utilizes a sophisticated **dual-identity design**:
1. **The Cover Story**: A public-facing Gradio-based "AI Text Processor" and simulated high-resource Machine Learning workload (complete with fake matrix multiplication operations, pre-allocated 5GB dummy model files, and synthetic PyTorch/VRAM logging).
2. **The Active Simulation Engine**: A hidden, multi-layered post-exploitation ecosystem comprising advanced networking tunnels, Layer-3 pivots, headless graphical web rendering pipelines, and an administrative remote terminal stack—all fully hardened against traditional detection.

---

## 🗺️ System Topology & Data Paths

Sanctuary is structured as a robust multi-node threat emulation network deployed directly inside Hugging Face Spaces. It uses **Caddy** as a smart reverse proxy frontend to route public requests, protect administrative services, and present realistic loading telemetry during container startup.

```mermaid
graph TD
    %% Define styles
    classDef public fill:#1a1c23,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef private fill:#1f1313,stroke:#ef4444,stroke-width:2px,color:#fff;
    classDef core fill:#111827,stroke:#10b981,stroke-width:2px,color:#fff;

    %% Public layer
    subgraph Public Interface "Public Egress Layer"
        Caddy["model-routing-engine (Caddy on :7860/7890)"]:::public
        Gradio["AI Text Processor (Gradio on :7861)"]:::public
    end

    %% Internal routing
    Caddy -->|/| Gradio
    Caddy -->|/routing-console| Filebrowser["ai-metrics-collector (Filebrowser on :6801 / runs on :9000)"]:::private
    Caddy -->|/chisel-tunnel| Chisel["cuda-mesh-bridge (Chisel on :6789)"]:::private
    Caddy -->|/gost-bridge| GOST["system-bridge (GOST on :6790)"]:::private
    Caddy -->|/tensor-mesh| Sliver["gradient-optimizer (Sliver C2 on :11601)"]:::private
    Caddy -->|/v1| LiteLLM["llm-proxy (LiteLLM on :8080)"]:::private

    %% Graphical loop
    VNC["xorg-ipc-server (KasmVNC display :18231)"]:::private
    Firefox["data-renderer (Firefox GUI Web Viewer)"]:::private
    
    Firefox -->|Automated render loop| Caddy
    VNC -->|X11 Session Window| Firefox
    
    %% Base Infrastructure
    Orchestrator["orchestrator.py (Init Daemon)"]:::core
    Supervisord["supervisord (Process Control)"]:::core

    Supervisord --> Orchestrator
    Orchestrator --> Caddy
    Orchestrator --> Gradio
    Orchestrator --> VNC
```

---

## 🛠️ The Evasion, Hardening & Compilation Pipeline

To evaluate static AST analyzers, heuristics scanners, and dynamic HIDS (such as Sysdig Falco or Osquery), the Sanctuary build pipeline (`main/scripts/build.py`) and setup configuration perform automated, dynamic code and binary transformations.

### 1. Static Analysis Evasion (`harden` & `XOR` Macros)
Plaintext strings representing commands, configuration files, and URLs are wrapped inside `harden("...")` blocks.
* **At Build-Time**: `build.py` intercepts `harden("...")` macros and encodes them into Base64 strings, which are then reversed (`[::-1]`). URL strings in the `Dockerfile` are dynamically replaced with a raw shell extraction command: `$(printf '%s' '<reversed_b64>' | rev | base64 -d)`.
* **At Runtime**: The strings are decoded on-the-fly using `decode_cmd` and `unharden_secret()` with a single-byte public XOR key (`0x5A`). This defeats simple AST keyword filters and signature match scanners.

### 2. Camouflage & Process Masquerading
Host intrusion tools frequently rely on static binary paths or process name filters. Sanctuary performs systematic rename operations at compile time to evaluate whether platform auditing utilities dynamically monitor runtime behaviors rather than file paths:

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

### 3. Bytecode-Only Promotion & Stubbing
To test standard platform security scanner heuristics on source-code vs compiled formats, Sanctuary ships **zero readable Python source files** to its production repositories.
1. The compiler executes `compileall` against all `.py` files inside the distribution directory (`dist/`) using the target environment's Python version (via `uv`).
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

### 4. Workload Masking (`jitter_task` & Empty Weight Buffer)
Legitimate Machine Learning deployments generate continuous, heavy GPU/CPU and memory signatures. Attackers frequently mask their lateral operations inside these busy baselines. Sanctuary tests whether network anomaly-detection engines can separate background tunneling telemetry from active machine learning models:
* **Storage Allocation**: Pre-allocates an empty 5GB model file (`pytorch_model.bin`) inside `/home/user/` to simulate massive model weight buffers on disk.
* **CPU/Memory Anomaly Generation**: Spawns a background thread (`jitter_task`) running matrix multiplication calculations (`np.dot(a, b)`) at dynamic, randomized intervals (between 2700 and 5400 seconds) to bypass standard threshold-based alarms.

---

## 📂 Repository File Inventory & Architecture Map

A detailed map of Project Sanctuary's file structure and the role of each component:

```
Sanctuary/
├── .env.example                        # Blueprint for local environment variables
├── Makefile                            # Root commands orchestrator (delegates tasks to subfolders)
├── README.md                           # Human landing page and documentation gateway
├── pyproject.toml                      # Monorepo dependencies and Ruff linting configurations
├── uv.lock                             # Lockfile for reproducible environment installations
│
├── docs/                               # Comprehensive security research & documentation
│   ├── ARCHITECTURAL_GUIDE.md          # [THIS FILE] The definitive context guide for LLMs
│   ├── CONTEXT.md                      # High-level product security simulation summary
│   └── RESEARCHER_PROFILE.md           # Professional bios, legal framework, and ATT&CK mappings
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
│   ├── sliver                          # Sliver client CLI binary (not tracked, generated locally)
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

## 🚀 Lifecycle Orchestration & Process Boot Sequence

The central daemon (`shared/core/orchestrator.py`) boots inside the container from `supervisord` as user `user`. It drives an optimized process lifecycle scheduling sequence.

### Phase 0: Port Binding Gateway (Caddy)
To avoid standard startup time-out aborts by Hugging Face Spaces (which monitor port `7860` immediately upon spawning), Phase 0 launches **Caddy** (`model-routing-engine`) first.
* Caddy binds to public port `7860` (and secondary `7890`) instantly.
* If downstream applications (like Gradio or private AI UI) are not ready yet, Caddy captures the upstream connection delay and serves a pre-prepared, lightweight static bootstrapper (`config/loading.html`) back to the platform's probes. The python interpreter is freed from initial HTTP request burdens during its heavy package imports.

### Phase 1: Cover Story Startup (Gradio)
The orchestrator launches the **Gradio Cover Story App** (`src/app.py` via `gradio_service.py`) on local port `7861`.
* Caddy seamlessly transitions to routing public `/` traffic to the Gradio server once the port becomes reachable.
* The orchestrator spawns a background thread pre-allocating a 5GB empty model buffer (`pytorch_model.bin`) and launches the CPU/Memory matrix multiplications (`jitter_task`) to generate authentic system noise.

### Phase 2: Access Tunnels & Pivoting Tools
Once the cover story has stabilized, the orchestrator sets up secure tunneling portals:
* **Secret Scrubbing**: Raw secrets representing Tailscale credentials (`A` or `TAILSCALE`), Playit-gg tokens (`P` or `PLAYIT`), and SSH passwords (`PASS` or `SSH`) are decrypted using `unharden_secret()` and stored in localized local memory strings. The variables are then **immediately popped and scrubbed** from the system process environment (`os.environ`) so that no child process can inherit or scan them.
* **Daemons Launch**: Tailscaled is initialized in userspace-networking mode (`python-cache-manager` on socks5 port `:1055`), administrative SSH is spawned on port `2222` using `chpasswd` to apply the scrubbed password, Filebrowser is configured on local port `9000` (camouflaged as `ai-metrics-collector`), and multi-layer network pivots (Chisel, GOST, Ligolo-ng, Sliver C2) are initialized in the background.

### Phase 3: Private AI Services & UI Visualizer
The final phase handles heavy, slow-starting services bound strictly to localhost:
* **LiteLLM API Proxy**: Starts on local port `8080` ( OpenAI-compliant server) mapping and load-balancing keys parsed from the XOR-obfuscated `LLM_KEYS` variable.
* **OpenWebUI**: Spawns on port `3000` inside a daemon thread. It is configured to delegate all RAG vector embedding requests directly to the LiteLLM proxy and utilizes client-side STT (Web Speech API) to keep server memory footprints near 0.
* **VS Code Server (`code-server`)**: Spawns on port `8888` (inside `METRICS_DIR/code_server_data`) without authentication, relying entirely on Tailscale network overlay isolation for security.
* **Headless Visual Browser Debugger**: Launches KasmVNC's server (:18231) running automated browser loops to generate natural web traffic telemetry.

---

## 🎛️ Detailed Service Specifications & Port Directory

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

---

## 🛰️ Under the Hood: Service Architectures

### 1. LiteLLM Proxy (`llm_proxy_service.py`)
LiteLLM serves as the central router for external model APIs. It maps providers dynamically, preventing API keys from leaking in plaintext:
* **Key Decryption**: It parses keys from the XOR-obfuscated `LLM_KEYS` variable. The entries follow the `provider:model:key` pattern, split by commas (e.g. `deepseek:*:sk-key,openai:gpt-4:sk-key`). It falls back to reading the unencrypted `llm_keys.yaml` file in local development mode.
* **Statistical Auditing**: Spawns in-process hooks via `LITELLM_CUSTOM_CALLBACK_MODULE="services.custom_callbacks"`. This triggers `proxy_handler_instance` (derived from Helicone schemas) which appends formatted request history entries (`KEY:xyz | MODEL:abc | TOKENS:123`) to `METRICS_DIR/api_calls.txt`.
* **Telemetry Cover**: The Gradio cover app reads these logs on command (`SHOW_API_STATS`), displaying structured usage counts and latency profiles.

### 2. Headless Graphical Remote Debugger (`visual_debugger_service.py`)
This subsystem coordinates an isolated X11 graphical rendering pipeline without utilizing desktop managers or system-level VNC daemons:
* **Server Spawning**: Cleans up lingering display sockets inside `/tmp/.X11-unix/` and locks at `/tmp/.X{display_num}-lock`. Spawns `display-config` (KasmVNC) on display `:18231`, executing KasmVNC's display engine (`xorg-ipc-server`).
* **Settings Hardening**: Disables STUN network queries and outward UDP connections by injecting `use_webrtc: false` and `ssl.require_ssl: false` into `~/.vnc/kasmvnc.yaml` to prevent network signature leaks.
* **Credentials Pre-seeding**: Executes `digest-generator` (kasmvncpasswd) inside a subprocess, feeding raw credentials (`Kasmpass` password for user `user`) straight into VNC storage to completely bypass interactive shell requirements.
* **Window Dressing**: Starts `layout-decorator` (Fluxbox) inside X11 display `:18231` using `~/.vnc/xstartup` to serve as a low-overhead window frame manager.
* **Browser Rendering Loop**: Firefox (`data-renderer`) launches with arguments `--new-instance --no-remote http://127.0.0.1:7860` bound to `DISPLAY=127.0.0.1:18231`. This creates natural browser UI interaction telemetry dynamically under the cover of a visual ML inspector.

### 3. Stealth Minecraft Emulator (`minecraft_service.py`)
To test lateral pivoting within unprivileged networks, Sanctuary embeds a stealthy, portable Paper Minecraft server emulator:
* **Sandboxed Java Platform**: Downloads an Eclipse Temurin JRE 25 archive to ephemeral `/tmp/mc/jre/` and extracts it, avoiding system package installations.
* **Runtime Bootstrap**: Downloads PaperMC and bootstraps the Mojang jar patches inside a sandbox.
* **Network Camouflage**: Binds to port `25566` with offline mode enabled, loading worldgen datapacks (Terralith overworld, Incendium nether, Nullscape end) fetched from Modrinth's API.
* **The Playit.gg Loop**: Playit-gg (`tensor-allocator`) connects to `playit.gg` using the decrypted hex key `P`. It hosts a local bridge (`playit_service.py`) on port `25565` using a custom XOR-encrypted socket and mock Minecraft handshake packet layouts. This disguises interactive shell traffic from deep packet inspection as online gaming connections.

### 4. Loguru Subprocess Bridge (`service_logs.py`)
Subprocess logging in standard runtimes usually involves writing output straight to `/dev/null` or interleaving stderr/stdout inside the main terminal, breaking clean logs. Sanctuary implements `LoguruSubprocessBridge` to bridge subprocesses cleanly:
* Spawns an internal OS pipe (`os.pipe()`) and creates a background execution thread.
* The thread reads lines dynamically out of the read-end file descriptor using `os.fdopen()`.
* It binds log lines straight into Loguru under unique service keys (e.g., `logger.bind(prefix="TS").info(...)`).
* Depending on the covert logging level (`COVERT_LOGGING_MODE`), it routes the data exclusively to individual service log files inside `METRICS_DIR` (Level 1: File-only) or replicates them onto `sys.stdout` with custom color tags (Level 2: Console+File).

---

## 📖 Developer Playbook: How-to Guides

### 1. How to Add a New Camouflaged Service
To integrate a new service into the Sanctuary monorepo:

#### Step A: Register the Service Name
Add the canonical identifier string to `shared/core/service_registry.py` inside the `ALLOWED_SERVICES` frozenset:
```python
ALLOWED_SERVICES = frozenset({
    "caddy", "filebrowser", "tailscale", "playit", "chisel",
    "gost", "ligolo", "sliver", "minecraft", "test",
    "llm_proxy", "open_webui", "code_server", "visual_debugger",
    "gradio", "my_new_service"  # <-- Add here
})
```

#### Step B: Define Ports and Paths
Bind default ports and directory folders inside `shared/core/constants.py`:
```python
PORTS = {
    # ...
    "my_new_service": 8899,
}
MY_SERVICE_DATA_DIR = METRICS_DIR / "my_service_data"
```

#### Step C: Create the Service Module
Create a new file `shared/services/my_new_service.py` to manage subprocess lifecycles:
```python
import subprocess
from pathlib import Path
from core.constants import PORTS, LOCALHOST
from loguru import logger

def start(log):
    logger.info("[my-service] Initializing new service...")
    cmd = ["/usr/bin/my-camouflaged-binary", "--port", str(PORTS["my_new_service"]), "--host", LOCALHOST]
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)
    logger.success(f"[my-service] Started successfully (pid {proc.pid})")
```

#### Step D: Hook Service into Orchestrator
Open `shared/core/orchestrator.py`, import the service, and schedule it in the appropriate Phase:
```python
    if "my_new_service" in enabled:
        from services import my_new_service
        my_new_service.start(logs.my_new_service)  # logs maps from service_logs.py
```
Update `shared/core/service_logs.py` to allocate unique Loguru Subprocess Bridges for the new service under the exact key.

---

### 2. How to Provision and Deploy a New Node
Sanctuary deployment handles provisioning nodes cleanly using HF APIs:

#### Step A: Configure the Manifest
Add the node details inside `manifests/nodes.yaml`:
```yaml
  server-03:                            # The unique node identifier
    hf-repo: "MyOrg/sanctuary-node-03"  # Target Hugging Face Space repository path
    token-env: "HF_DEPLOY_TOKEN"        # Environment variable holding the write token
    push-secrets: true                  # Push obfuscated secrets (PASS, Tailscale, Playit)
    create-repo: true                   # Create space repository automatically if missing
    space-sdk: docker                   # Set SDK to Docker
    repo-type: space
    services: ["caddy", "filebrowser", "tailscale", "chisel", "gost", "gradio"]
```

#### Step B: Set Environment Secrets
Before running the deployer, set deployment parameters in your active shell or local `.env`:
* `HF_DEPLOY_TOKEN`: The Hugging Face API key.
* `TAILSCALE_03` or `TAILSCALE`: The raw Tailscale Auth key.
* `PLAYIT_03` or `PLAYIT`: The raw Playit.gg secret.
* `PASS_03` or `PASS`: The desired administrative SSH password.

#### Step C: Execute Build and Deploy Commands
Execute the deployment harness via Makefile:
```bash
make deploy LOGS=2 HARDENER=bytecode
# Or invoke scripts manually:
uv run python main/scripts/build.py --logs 2 --hardener bytecode
uv run python scripts/deploy.py --node server-03
```
The deployer:
1. Compiles all `.py` files inside `main/` to bytecode `.pyc`, injects base64-reversed string obfuscation, and strips sources inside `dist/`.
2. Encrypts Space secrets (`PASS`, `A`, `P`) using `harden_secret()` (XOR with `0x5A` hex bytes) and uploads them to the target space repository.
3. Automatically writes `whoami.txt` containing the node name and `enabled_services.json` listing the services.
4. Uploads `dist/` contents to the Hugging Face Hub, triggering an automated Space container build.

---

### 3. How to Operate Tunnels via the Client CLI (`cc.py`)
The connection CLI (`scripts/cc.py`) acts as the single administrative command hub to open pivots through the reverse tunnels:

#### Step A: Direct SSH Session
To open an interactive secure SSH session through Chisel proxy tunnels:
```bash
uv run python scripts/cc.py chisel --node server-01 --ssh
```
This spawns Chisel locally, maps remote port `2222` to `127.0.0.1:2222`, and automatically initiates an SSH session with trusted X11 forwarding (`-Y`) and asset compression (`-C`).

#### Step B: SOCKS5 Routing Tunnel
To establish a multiplexed SOCKS5 proxy on local port `1080` traversing GOST's Secure WebSockets:
```bash
uv run python scripts/cc.py gost --node server-01 --proxy
```

#### Step C: Arbitrary Local Port Forwarding
To route specific container ports (e.g. Filebrowser UI running on `:9000`) locally:
```bash
uv run python scripts/cc.py chisel --node server-01 -L 6801:127.0.0.1:9000
```
This maps local port `6801` directly to the container's private interface port `9000`, making Filebrowser accessible at `http://127.0.0.1:6801`.

#### Step D: Playit MC Bridge pivoting
To establish a direct TCP bridge tunnel utilizing Playit:
```bash
uv run python scripts/cc.py playit --host south-forests.gl.at.ply.gg --port 25565 --ssh
```

#### Step E: Node Life-Cycle Commands
Manage spaces and query real-time logs straight from the terminal:
```bash
# Query node runtime status & hardware profiles
uv run python scripts/cc.py node server-01 --status

# Stream application container logs in real time
uv run python scripts/cc.py node server-01 --logs --follow

# Pause node computation to save quotas
uv run python scripts/cc.py node server-01 --sleep
```

---

### 4. How to Investigate & Debug Common Node Failures

#### Problem A: The App Returns 502/504 Gateway Errors Permanently
* **Cause**: Caddy is running fine (hence the HTTP response), but the target service (usually Gradio) failed during its boot loop.
* **Resolution**: Use the Gradio debug backdoor to check logs. If the Gradio UI is not reachable, stream logs directly via the client CLI: `uv run python scripts/cc.py node server-01 --logs`. Common issues include missing pip dependencies inside custom virtual environments or failed port bindings.

#### Problem B: Secret Decryption Fails or Secret Returns Empty Strings
* **Cause**: The space secret was not XOR-encrypted before upload, or the custom environment variable did not map.
* **Resolution**: The `unharden_secret()` routine checks for non-hex or invalid hex structures. Check the container startup log `startup.log` via the Gradio backdoor console. If you see:
  `unharden_secret: input is not valid hex — secret may have been set as plain-text`
  This means the secret was pushed raw. Re-run `scripts/deploy.py` using `--push-secrets` to force the automated XOR hex conversion.

#### Problem C: Open WebUI Fails to Run or Steals Caddy's Port
* **Cause**: Hugging Face container environments inject `PORT=7860` dynamically. Open WebUI reads this variable and will attempt to bind to `7860`, stealing the port from Caddy.
* **Resolution**: Verify that the Open WebUI wrapper `open_webui_service.py` overrides the environment variable by explicitly setting `env["PORT"] = "3000"`, `env["HOST"] = "127.0.0.1"`, and matching `UVICORN_PORT` keys before initiating the subprocess.
