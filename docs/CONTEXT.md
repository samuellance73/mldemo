# Project Context: Red Team Campaign Environment

## Simulation Overview
This project is an advanced, multi-node threat simulation environment designed for deployment within Hugging Face Spaces. It functions as an authorized, internal security evaluation target modeled by the Product Security team. 

The environment uses a Gradio AI interface and synthetic machine learning process signals (such as fake memory-allocation logs and background mathematical loops) as a **functional cover story**. This setup allows researchers to evaluate platform boundary detection, network egress monitoring, and process auditing under realistic, behaviorally masked post-compromise scenarios.

---

## 🛠️ Evasion & Compilation Engineering (`scripts/build.py`)

The pipeline performs the following dynamic transformations to simulate advanced threat actor tactics:

1. **Static Analysis Evasion**: Replaces `harden("...")` blocks inside core scripts with base64-reversed strings during the build phase to evaluate static AST scanners.
2. **Process Masquerading**: Renames administrative, proxy, and visual debugging binaries at runtime to mimic innocent machine learning processes, testing whether host intrusion detection systems (HIDS) rely on static binary paths or dynamic behavioral auditing.
3. **Workload Masking**: Executes background mathematical operations (`jitter_task`) and pre-allocates an empty 5GB model file (`pytorch_model.bin`) to generate realistic system noise. This tests whether platform anomaly-detection algorithms can isolate background tunnels from standard, high-resource machine learning workloads.

---

## 🛰️ Active Simulation Components

1. **Adversary Simulation Console (Sliver C2)**: Runs as the background daemon `gradient-optimizer` to test mutual-TLS (mTLS) network telemetry.
2. **Layer-3 Pivot Hub (Ligolo-ng)**: Configured as the proxy daemon `neural-route-controller` to test the containment of unprivileged network interfaces.
3. **Multi-Layer Tunnel Stack (Chisel / GOST / Tailscale)**: Configured to test deep-packet inspection (DPI) boundaries and persistent WebSocket traffic detection.
4. **Standalone Visual Browser (Firefox)**: Extracted and executed as `data-renderer` directly on a raw X11 display buffer (`xorg-ipc-server`) without desktop session managers to evaluate unprivileged graphical rendering detection.