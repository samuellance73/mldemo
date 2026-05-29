# Sanctuary 🌌

> *"We are creating a world that all may enter without privilege or prejudice accorded by race, economic power, military force, or station of birth... a world where anyone, anywhere may express his or her beliefs, no matter how singular, without fear of being coerced into silence or conformity."*
> — John Perry Barlow, *A Declaration of the Independence of Cyberspace* (1996)

Sanctuary is a unified, corporate-grade monorepo containing a secure, highly decoupled, camouflage-ready distributed application architecture. It combines a robust machine learning backend service with a standalone, custom-configured frontend container.

---

## 📂 Repository Structure

The project is organized as a clean **Workspace Monorepo** with decoupled sibling projects:

```
Sanctuary/                  <─── Unified Monorepo Parent Root
├── main/                   <─── Core Python Backend (Camouflaged ML node)
│   ├── config/             <─── Process manager (supervisord) & network configurations
│   ├── manifests/          <─── Node layouts and active deployment state manifests
│   ├── scripts/            <─── Minification, obfuscation, and deployment pipelines
│   └── src/                <─── Encryption layers, core orchestrator, and service modules
├── kasm-workspace/          <─── Standalone Kasm Workspace Container
│   ├── Dockerfile          <─── Port-customized, permission-patched deployment
│   └── README.md           <─── Hugging Face Space configuration and documentation
├── Makefile                <─── Top-level command forwarder
└── README.md               <─── Monorepo documentation (this file)
```

---

## 🛠️ Commands & Automation

Automation targets are managed by the top-level root `Makefile`. You can run these commands from the root directory to control the monorepo pipeline:

| Command | Action | Forwarded Target |
| :--- | :--- | :--- |
| `make build` | Minifies backend scripts, compiles assets, and updates build state | `make -C main build` |
| `make deploy` | Resolves all nodes (including UI custom folders) and deploys them to Hugging Face | `make -C main deploy` |
| `make clean` | Wipes build targets in `main/dist/` while safely preserving local `.git` caches | `make -C main clean` |

> [!NOTE]
> You can pass an optional `LOGS` variable to command targets to control covert logging levels:
> - `LOGS=0` : Logging fully disabled
> - `LOGS=1` : Covered file-only logging (default)
> - `LOGS=2` : Console + File debugging logging
> 
> *Example:* `make build LOGS=2`

---

## 🛰️ Node Deployments (`manifests/nodes.yaml`)

Sanctuary automates the deployment of multiple distributed nodes directly to Hugging Face Spaces:

- **Core Camouflaged Backend Nodes** (`server-01` through `server-06`): Exposes Gradio apps running stealth encrypted reverse proxies, Minecraft servers, Tailscale mesh connectors, and Sliver shells inside the target environments.
- **Frontend Gateway / Desktop** (`kasm-desktop`): Deploys a standalone, custom-configured Kasm Workspaces GUI environment with integrated browser-based VNC access.