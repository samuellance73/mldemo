# Sanctuary: System Architecture and Technical Reference 🌌

This document serves as the definitive architecture reference manual for Project Sanctuary. It maps the runtime patterns, network topologies, memory lifecycles, and cryptographic custody loops executed across the monorepo.

---

## 1. System Overview & Edge Routing Matrix

Project Sanctuary implements a multi-tier runtime architecture deployed inside an unprivileged container context. The front edge is managed by **Caddy** (camouflaged as `model-routing-engine`), which acts as an ingress gateway, SSL termination layer, and reverse proxy.

```
                    [ Hugging Face Edge Ingress ]
                                │ (HTTPS)
                                ▼
                       ┌─────────────────┐
                       │   Caddy Proxy   │ (Port 7860 / 7890)
                       └────────┬────────┘
                                │
        ┌───────────────────────┼────────────────────────┬─────────────────────┐
        ▼ (/v1)                 ▼ (/chisel-tunnel)       ▼ (/routing-console)  ▼ (Default /)
┌──────────────┐        ┌──────────────┐         ┌──────────────┐      ┌──────────────┐
│   LiteLLM    │        │ Chisel Proxy │         │ Filebrowser  │      │ FastAPI App  │
│ (Port 8080)  │        │ (Port 6789)  │         │ (Port 9000)  │      │ (Port 7861)  │
└──────────────┘        └──────────────┘         └──────────────┘      └──────────────┘
```

### Complete Network Port Directory

The orchestrator manages 16 distinct service endpoints bound to localized loopback interfaces, mapped internally as follows:

| Service Identifier | Constant Port | Protocol | Binding Interface | Process Camouflage Name | Role / Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Caddy Ingress** | `7860` | HTTP | `0.0.0.0` | `model-routing-engine` | Public gateway reverse proxy |
| **Caddy Secondary** | `7890` | HTTP | `0.0.0.0` | `model-routing-engine` | Secondary routing and pivoting port |
| **Portal Gateway** | `7861` | HTTP | `127.0.0.1` | `python3` (app.py) | Cover page and core FastAPI endpoint |
| **SSH Server** | `2222` | SSH | `127.0.0.1` | `sshd` | Interactive terminal shell |
| **Chisel Tunnel** | `6789` | WS | `127.0.0.1` | `cuda-mesh-bridge` | Reverse SOCKS5 TCP-over-WS tunnel |
| **GOST Proxy** | `6790` | MWS | `127.0.0.1` | `system-bridge` | Multiplexed Secure WebSocket relay |
| **Model Sync** | `6795` | HTTP | `127.0.0.1` | Internal sync | Model weight synchronization port |
| **Sliver C2 / Ligolo** | `11601` | mTLS / TCP | `127.0.0.1` | `gradient-optimizer` | Command-and-control server interface |
| **LiteLLM Proxy** | `8080` | HTTP | `127.0.0.1` | `litellm` | Model-agnostic OpenAI API gateway |
| **Filebrowser** | `9000` | HTTP | `127.0.0.1` | `ai-metrics-collector` | Web filesystem administration console |
| **Tailscale SOCKS5** | `1055` | SOCKS5 | `127.0.0.1` | `python-cache-manager` | Mesh VPN userspace SOCKS5 server |
| **Playit XOR Bridge** | `25565` | TCP | `0.0.0.0` | Python bridge | Minecraft-handshake tunnel wrapper |
| **Minecraft Server** | `25566` | TCP | `127.0.0.1` | `java` (Paper JRE 25) | Local Paper server backup backend |
| **Open WebUI** | `3000` | HTTP | `127.0.0.1` | `open-webui` | Browser UI for LiteLLM router |
| **Code Server** | `8888` | HTTP | `127.0.0.1` | `code-server` | Visual Studio Code in the browser |
| **KasmVNC Web Stream**| `8501` | HTTP/WS | `127.0.0.1` | `display-config` | Headless visual stream streaming port |
| **Scramjet Proxy** | `8085` | HTTP/WS | `127.0.0.1` | Python / Node | Web proxy & network bypass gateway (`/proxy`) |

---

## 2. Unified Boot Sequence and Orchestration Lifecycle

Subprocesses are instantiated using a non-blocking, multi-phase boot pipeline scheduled inside `src/sanctuary/core/orchestrator.py` to satisfy cloud runtime health check timeouts.

```
[Phase 0: Base Ingress] ──► [Phase 1: Cover Workload] ──► [Phase 2: Secret Scrubbing]
                                                                    │
[Phase 5: Visual Stream] ◄── [Phase 4: Local Dev Stack] ◄── [Phase 3: Secure Access Ports]
```

### Phase 0: Base Ingress Initialization
* **Action:** Starts Caddy (`model-routing-engine`) instantly on public ports `:7860` and `:7890`.
* **Objective:** Serve a static `loading.html` page directly from disk. This ensures Hugging Face container health monitors receive a valid `HTTP 200` response within the 30-second boot timeout window, preventing deployment failures.

### Phase 1: Cover Workload Launch
* **Action:** Spawns the Portal Gateway FastAPI application (`app.py` via `portal_service.py`) on local port `7861`.
* **Telemetry Generation:**
  * Allocates a sparse 2GB file named `pytorch_model.bin` to simulate a large machine learning model.
  * Launches the background task `jitter_task()` to run numpy matrix dot-product operations at randomized intervals (between 45 and 90 minutes) to emulate standard ML execution workloads.

### Phase 2: Secret Scrubbing & Sanitization
* **Action:** Reads, decrypts, and sanitizes environment-passed credentials.
* **Objective:** Clean system memory before starting heavy applications (detailed in Section 3).

### Phase 3: Secure Access Ports
* **Action:** Launches the core tunnels and local network interfaces.
  * Starts Tailscale in userspace networking mode (SOCKS5 on port `1055`, routing state to `~/.torch_metrics/`).
  * Establishes Filebrowser on local port `9000` and generates database schemas in `/home/user/filebrowser.db`.
  * Starts the SSH server on port `2222` with the decrypted password.
  * Spawns Chisel, GOST, and Sliver servers.

### Phase 4: Local Dev Stack Launch
* **Action:** Launches developer workspaces and AI interfaces.
  * Spawns the LiteLLM API router on port `8080` (utilizing credentials loaded from `LLM_KEYS`).
  * Starts Code Server on port `8888` under userspace loopback isolation.
  * Dispatches Open WebUI's installation and startup tasks to a background thread to prevent blocking the main runtime thread.

### Phase 5: Visual Stream Debugger
* **Action:** Initializes the virtual display context and visual streaming pipeline (detailed in Section 5).

---

## 3. Cryptographic Custody and Secret Sanitization

Sanctuary implements a strict secret-sanitization loop to ensure that sensitive API tokens and credentials (`TAILSCALE`, `PLAYIT`, `PASS`, `CLOUDFLARE`, `LLM_KEYS`) never leak through dynamic environment scans or container memory inspect tasks.

```
   [Hugging Face Space Settings] (Encrypted Hex Strings)
                 │
                 ▼ (Container Boot)
         [os.environ]
                 │
                 ▼ (orchestrator.py loads secrets)
        [unharden_secret()] ──► Memory Strings
                 │
                 ▼
          [os.environ.pop()] ──► [Empty Environment Space]
                 │
                 ▼ (Subprocesses launched)
     Subprocesses run with sanitized environmental parameters
```

### The Sanitization Protocol
1. **Extraction:** On startup, `orchestrator.py` retrieves obfuscated hex secrets injected by the container engine.
2. **Decryption:** The unhardening function performs a single-byte XOR calculation using static key `0x5A`. This acts as a basic protection layer to hide plain text secrets from static platform analyzers.
3. **Purging:** The orchestrator immediately calls `os.environ.pop()` on all original environment variables, erasing them from the process environment block.
4. **Execution:** Subprocesses are instantiated with clean, sanitized environments. Keys are passed to children exclusively via safe loopback channels or secure standard input.

### XOR Obfuscation Reference Implementation

```python
# src/sanctuary/common/utils.py

XOR_KEY = 0x5A

def unharden_secret(hex_str, key=XOR_KEY):
    """XOR-unhardens a hex-encoded secret."""
    if not hex_str:
        return ""
    try:
        raw_bytes = bytes.fromhex(hex_str.strip())
        unhardened_bytes = bytes([b ^ key for b in raw_bytes])
        return unhardened_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return hex_str
```

---

## 4. Evading Static AST Scans: Obfuscation and Bytecode-Only Deployment

To prevent static AST (Abstract Syntax Tree) scanners from analyzing the codebase inside the repository, Project Sanctuary implements a secure compilation pipeline (`main/scripts/build.py`) that strips readable source code and ships only compiled bytecode.

### Bytecode Compilation & Promotion Mechanics

```
               [build.py] Raw Source Code
                     │
                     ▼ (compileall module)
     Compiled Bytecode inside __pycache__/foo.cpython-312.pyc
                     │
                     ▼ (Promote .pyc out of __pycache__)
      Bytecode promoted to root package path: foo.pyc
                     │
                     ▼
             [unlink() original .py]
                     │
                     ▼
  Container launches utilizing a secure Python Loader Stub
```

1. **AST Transformation:** At build time, the compiler searches for the custom `harden("...")` macro, base64-encodes and reverses the target arguments, and writes them to disk.
2. **CPython Compilation:** Executes `compileall` against the generated `dist/` directory using the target container's CPython compiler version (currently `3.12` to align with the Ubuntu 24.04 runtime).
3. **Bytecode Promotion:** In standard Python setups, compiled bytecode inside `__pycache__` is only resolved if the matching `.py` source file exists on disk. To bypass this, the build script copies `.pyc` files directly to the root package directory (e.g., `dist/sanctuary/core/orchestrator.pyc`), completely stripping the version tag from the filename.
4. **Source Destruction:** The original `.py` source code is securely unlinked (`deleted`) from the directory tree, leaving only bytecode files on disk.
5. **Memory-Only Loader Stub:** For execution entry points that require manual path calls (such as `orchestrator.py` via Supervisord), the build engine writes a thin python loader stub:

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

---

## 5. Headless Display Virtualization & Browser Automation

The platform includes a headless graphical workspace (`src/sanctuary/services/visual_debugger_service.py`) that runs independent graphical automation tasks without a physical desktop screen.

```
       [ KasmVNC Server (:18231) ] ──► (Websocket Display Server)
                    │
                    ▼ (Local UNIX Sockets)
   [ Fluxbox Layout Window Manager ]
                    │
                    ▼ (DISPLAY=:18231)
  [ Firefox (data-renderer) automation ] ──► Loops against localhost:7860
```

### Visual Subsystem Components
1. **X11 Display Context:** Instantiates KasmVNC's display engine (camouflaged as `xorg-ipc-server`) bound to display address `:18231`.
2. **Sandbox Protection Configuration:**
   * Generates a hardened `kasmvnc.yaml` file that programmatically disables external WebRTC signaling and STUN server lookup requests to prevent outbound UDP leaks.
   * Leverages mock SSL paths pointing directly to system parameters (such as `/etc/hostname`) to bypass connection crashes.
3. **Automatic Credentials Setup:** Runs the `digest-generator` tool non-interactively to pre-seed VNC accounts directly with localized variables, eliminating manual command steps.
4. **Window Management:** Spawns Fluxbox (`layout-decorator`) on display `:18231` using custom startup scripts to manage system window frames.
5. **Interactive Browser Automation:** Launches a headless Firefox instance (camouflaged as `/opt/render-engine/data-renderer`) targeted directly at Caddy's routing endpoint (`http://127.0.0.1:7860`). This runs persistent page interaction scripts to emulate standard user activity inside the container.

---

## 6. Storage and State Synchronization Engines

Project Sanctuary features dual-engine synchronization routines (`storage_sync_service.py` and `state_sync_service.py`) to manage persistent data across deployments without relying on persistent disk allocations.

### Sync Topology

```
                  ┌──────────────────────────────┐
                  │   State Stage Area (~/.sync) │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼ (Hugging Face API)                            ▼ (Rclone Sync Interface)
┌─────────────────┐                             ┌─────────────────┐
│   HF Dataset    │                             │ S3 / R2 Bucket  │
│ (Private Repo)  │                             │ (Secure Object) │
└─────────────────┘                             └─────────────────┘
```

### 1. Unified Sync Interface
Synchronization providers inherit from a clean, abstract contract to decouple platform execution logic:
```python
class BaseStorageProvider(ABC):
    @abstractmethod
    def pull(self, local_dir: Path) -> None: pass

    @abstractmethod
    def push(self, local_dir: Path, commit_message: str) -> None: pass
```

### 2. Hugging Face Datasets Driver
* **Pull Mode:** Downloads remote repository changes using `snapshot_download()` and filters out system metadata patterns (such as `.git*`).
* **Push Mode:** Commits local system changes using `HfApi().upload_folder()`, systematically purging deleted local resources on the remote endpoint via wildcard matching (`delete_patterns="*"`).

### 3. S3/R2 Rclone Adapter
* **Execution:** Spawns optimized, isolated subprocess calls using Rclone.
* **Security:** Instead of writing access credentials to a plain-text configuration file on disk, the provider injects sensitive tokens securely using runtime process variables:
  * `RCLONE_CONFIG_S3SYNC_ACCESS_KEY_ID`
  * `RCLONE_CONFIG_S3SYNC_SECRET_ACCESS_KEY`
  * `RCLONE_CONFIG_S3SYNC_ENDPOINT`

### 4. Continuous Background Sync Loop
When `state_sync` is enabled:
1. **Startup Restoration:** Performs a synchronous pull on boot to restore files from the remote storage provider.
2. **Periodic Checkpoints:** Launches a background thread to automatically push system updates to the remote storage provider every 30 minutes.
3. **Graceful Shutdown Hook:** Registers system traps (`SIGINT`, `SIGTERM`) to trigger a final, blocking backup run on shutdown before exiting.