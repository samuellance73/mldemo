---

## 🛠️ Evasion & Compilation Engineering (`scripts/build.py`)

Run `make build LOGS=1` (default) to output covert logs to files, `make build LOGS=2` to output to both console and files, or `make build LOGS=0` for a stealth production build. The pipeline performs the following defensive-evasion transformations:

1. **`src/core/`** → `dist/core/`
   - **`service_logs.py`**: Compiles logging levels based on the `LOGS` build flag, then minifies.
   - **`orchestrator.py`**: Resolves internal shell commands, replaces `OBFUSCATE("...")` blocks, and minifies.

2. **`Dockerfile`** → `dist/Dockerfile`
   - Dynamically translates URLs wrapped in `URL_OBFUSCATE("...")` to Base64-reversed decoding strings.
   - Strips all comments and `#` characters to present a minimal administrative footprint.

3. **`src/app.py`** → `dist/app.py`
   - Minifies the Gradio cover app using `python-minifier` to strip comments and docstrings.

4. **`src/services/`** → `dist/services/`
   - Iterates through Python modules under `src/services/`.
   - Replaces and obfuscates command strings wrapped in `OBFUSCATE(...)`.
   - Compiles and minifies python code to strip readable source identifiers.

After compilation, the target payload is structured inside `dist/` for deployment.

---

## 🛰️ Operator Connectivity & C2 Client (`scripts/cc.py`)

The operator-side command-line interface is designed to establish secure, covert loops back into the remote nodes. It implements four main tunneling and connection modes:

1. **Playit-gg (Minecraft XOR Disguise)**:
   - Establishes a local bridge forwarding to the remote Playit public tunnel address.
   - Utilizes a **Minecraft 1.20.2 login disguise**: handshake, login start, login success, then frames SSH data within XOR-encrypted `Login Plugin` packets on channel `bungeecord:main` (XOR `0x5A`) to bypass deep-packet inspection (DPI).
   - **CLI**: `--port` = public relay (usually `25565`); `--forward` = local SSH listen port (default `2222`).
   - Usage: `uv run python scripts/cc.py playit --host <host> --port 25565 [--forward 2222]`

2. **Chisel mode (`chisel`)**:
   - Establishes an HTTP/Websocket tunnel directly to the node's `/chisel-tunnel` endpoint, mapping local loops:
     - Local SOCKS5 Proxy: `1080`
     - SSH Forwarding: `2222 -> 127.0.0.1:2222`
     - Filebrowser Forwarding: `9000 -> 127.0.0.1:9000`
   - Usage: `uv run python scripts/cc.py chisel --node <node-name>`

3. **GOST mode (`gost`)**:
   - Connects directly to the multiplexed websocket proxy at `/gost-bridge` using `relay+mwss://` and forcing path parameters.
   - Supports:
     - Local SOCKS5 Proxy: `1080` (`--proxy-mode socks5`)
     - SSH Forwarding: `2222 -> 127.0.0.1:2222` (`--proxy-mode ssh`)
   - Usage: `uv run python scripts/cc.py gost --node <node-name> [--proxy-mode socks5|ssh]`

4. **Ligolo-ng mode (`ligolo`)**:
   - Manages Layer-3 tunneling. The pivot proxy runs on the Space, accepting reverse-connections from internal agents.
   - Usage: `uv run python scripts/cc.py ligolo hub --node <node> --info`

---

## 🕵️‍♂️ Process Masquerading (Runtime Camouflage Mappings)

To blend in with standard machine learning container runtimes, all administrative, proxy, and C2 binaries are renamed during container preparation to mimic native AI model processes:

| Disguised System Name       | Core Binary       | Operational Purpose                  |
|-----------------------------|-------------------|--------------------------------------|
| `python-cache-manager`      | `tailscaled`      | Secure mesh network daemon           |
| `py-cache-cli`              | `tailscale`       | Mesh network control CLI             |
| `ai-metrics-collector`      | `filebrowser`     | Covert file exfiltration manager     |
| `tensor-allocator`          | `playit-agent`    | Egress relay proxy                   |
| `cuda-mesh-bridge`          | `chisel`          | High-speed WebSocket egress proxy    |
| `system-bridge`             | `gost`            | Multiplexed tunnel proxy             |
| `neural-route-controller`   | `ligolo-ng proxy` | Layer-3 TUN pivot hub                |
| `gradient-optimizer`        | `sliver-server`   | Command and Control (C2) framework   |
| `display-compositor`        | `vncserver`       | Headless visual desktop launcher     |
| `display-config`            | `vncconfig`       | VNC clipboard sync manager           |
| `session-auth-tool`         | `vncpasswd`       | Password hash generator              |
| `ws-relay`                  | `websockify`      | WebSockets-to-TCP translator         |
| `data-renderer`             | `firefox`         | Standalone headless browser          |

All telemetry and execution logs are routed to a hidden cache directory: `/home/user/.torch_metrics/`
| Camouflaged Log Name | Target Service Log Output        |
|----------------------|----------------------------------|
| `ts_daemon.log`      | Tailscale daemon initialization  |
| `fb.log`             | Filebrowser exfiltration access  |
| `tm_daemon.log`      | Playit tunnel state and errors   |
| `chisel.log`         | Chisel connection telemetry      |
| `gost.log`           | GOST multiplexer events          |
| `ligolo.log`         | Ligolo proxy routing states      |
| `sliver.log`         | Sliver C2 server telemetry       |
| `nginx.log`          | Nginx ingress server logs        |
| `mc_daemon.log`      | Stealth Minecraft loop logs      |
| `startup.log`        | Master orchestrator boot record  |

---

## 📊 Backchannel Telemetry Access (Gradio Console Commands)

Operators can input specific diagnostic commands into the public Gradio interface to securely retrieve real-time logs and telemetry backchannels:

| Command Key              | Output Returned                 |
|--------------------------|---------------------------------|
| `SHOW_LOGS_TAILSCALE`    | Contents of `ts_daemon.log`     |
| `SHOW_LOGS_FILEBROWSER`  | Contents of `fb.log`            |
| `SHOW_LOGS_METRICS2`     | Contents of `tm_daemon.log`     |
| `SHOW_LOGS_CHISEL`       | Contents of `chisel.log`        |
| `SHOW_LOGS_GOST`         | Contents of `gost.log`          |
| `SHOW_LOGS_LIGOLO`       | Contents of `ligolo.log`        |
| `SHOW_LOGS_SLIVER`       | Contents of `sliver.log`        |
| `SHOW_LOGS_NGINX`        | Contents of `nginx.log`         |
| `SHOW_ALL_LOGS`          | Comprehensive multi-service log |
| `SHOW_LOGS_STARTUP`      | Boot logs and verification      |
| `SHOW_API_STATS`         | LiteLLM proxy call metrics      |

---

## 🎯 Per-Node Service Profiling (`manifests/nodes.yaml`)

Each deployment node specifies an optional list of `services` in the deployment manifest. The deployer (`deploy.py`) writes `config/enabled_services.json` at upload time. When the node boots, the orchestrator parses the JSON and launches only those active services, allowing distinct, node-specific threat profiles:

* **Full Pivot Node** (e.g., `server-01`): Runs `nginx`, `filebrowser`, `chisel`, `gost`, `ligolo`, `sliver`, and `visual_debugger` (Full proxying, visual browser debugging, and pivot capability).
* **Stealth Egress Node** (e.g., `server-02`): Runs `nginx`, `filebrowser`, `playit`, and `minecraft` (Covert exfiltration via vanilla gaming protocols).

### Secure Credential Injection (Hugging Face Secrets)
Sensitive values are passed securely using space secrets to prevent detection in repositories:
* **`A`**: Ephemeral Tailscale auth key (XOR-hex encoded)
* **`P`**: Playit tunnel credential token (XOR-hex encoded)
* **`PASS`**: Root SSH / Filebrowser authentication password (XOR-hex encoded)
* **`LLM_KEYS`**: Provider API keys for the LiteLLM load-balancer proxy (XOR-hex encoded)

All plaintext environment secrets are aggressively scrubbed from process memory immediately after successful service initialization.