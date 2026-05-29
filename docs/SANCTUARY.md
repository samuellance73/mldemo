# Sanctuary: Operational Red Team Simulation

> *"To understand the defense of an enclave, one must first map the ingenuity of its adversaries. We simulate the shadow not to live in it, but to ensure the light knows where to fall."*
> — Operational Security Log, Project Sanctuary (Ref: HF-RT-2026)

---

## 🌌 Operational Context & Scope

Project Sanctuary is an authorized platform-hardening research initiative designed and executed by a resident **Hugging Face Red Team** security engineer. 

Rather than relying purely on external checklists, this internal threat simulation adopts an offensive, "assume breach" posture. Its goal is to test the limits of Hugging Face's platform telemetry, ingestion validation pipelines, and runtime container isolation, ensuring that platform defenses are hardened against sophisticated, highly camouflaged persistence strategies.

---

## 🕵️‍♂️ The Narrative: An Adversary in the Enclave

### Phase 1: Static Analysis & The Ingestion Bypass
The campaign begins at the ingestion pipeline. Typical static scanners search container manifests (`Dockerfile` layers) for known administrative tools, shell-bound tunnels, and C2 agents. 

To evaluate the resolution limits of these scanners, Sanctuary implements **Ingestion Camouflage**:
* **Binary Metamorphosis**: High-value tools are renamed to look like standard machine learning pipelines. `tailscaled` is ingested as `python-cache-manager`; `gost` is compiled as `system-bridge`.
* **Hash Jitter & UPX Compaction**: Binaries are packed and appended with random byte-jitter streams to alter their cryptographic signatures, testing whether signature-based detections can identify the modified execution headers.
* **Build vs. Runtime Separation**: To bypass static build-time Dockerfile scanners entirely, the heaviest components of the environment—such as the desktop X11 packages, TigerVNC, and browser rendering engines—are omitted from the build phase. Instead, they are dynamically compiled and installed *at runtime* when the container boots, evaluating the latency and coverage of runtime threat scanners.

---

### Phase 2: The Cover Story (Camouflage of Presence)
A headless container running raw network proxies is an obvious anomaly. To satisfy platform liveness checks and human auditors, the simulation requires a believable "cover story."

Sanctuary deploys an innocent, functional **Gradio Text Processor** on the primary container port (`7860/7861`). 
* To a platform scanner or casual visitor, the Space appears to be a standard, low-overhead NLP demo.
* Behind this wrapper, traffic is secretly demultiplexed through a Caddy routing engine, mapping standard HTTPS requests to background tunneling endpoints (like `/chisel-tunnel` or `/gost-bridge`) while serving a branded loading page if the backend services are still initializing.

---

### Phase 3: Establishing Covert C2 & Pivot Points
Once the cover story is active, the simulation transitions to establishing command-and-control (C2) channels and evaluating platform escape constraints:
* **The Layer-3 Tunnel (Ligolo-ng)**: The proxy runs internally on the server, listening on port `11601` (masked as `/tensor-mesh` on the public route). External agents connect back to the hub, attempting to establish a virtual TUN interface on the host to simulate an adversary pivoting deep into internal cloud subnets.
* **The mTLS Console (Sliver C2)**: Disguised as `gradient-optimizer`, a headless Sliver daemon runs quietly, providing an encrypted, highly secure multi-player operational interface through mutual-TLS over port `31337`.
* **The Minecraft Handshake Disguise**: For networks where SSH and classic proxy protocols are strictly blocked, the red team implements a custom tunnel over public relays (Playit). Traffic is disguised as Minecraft 1.20.2 login packets, carrying XOR-encrypted SSH payloads hidden inside vanilla `Login Plugin` messages on the `bungeecord:main` channel.

---

## 🔬 Tactical Defense: What This Teaches Us

These simulations are designed to yield actionable insights for the Hugging Face security and platform engineering teams to harden platform boundaries:

1. **Over-reliance on Static Dockerfile Audits**: Scanners that only inspect the `Dockerfile` at build-time can be easily bypassed by runtime dynamic installation scripts. Defenders must implement continuous runtime behavioral analysis (e.g., monitoring out-of-order `apt-get` calls from non-root service users).
2. **Behavioral Process Monitoring**: While binary names like `Xtigervnc` or `tailscaled` can be renamed to `xorg-ipc-server` or `python-cache-manager`, their behavioral signatures (e.g., standard VNC port bindings, specific raw socket allocations, or memory footprint profiles) remain consistent. Defenses should alert on unprivileged users executing persistent raw sockets.
3. **Proxy Path Telemetry**: Standard web application firewalls (WAFs) often ignore websocket upgrades on subpaths like `/visual-debugger*` or `/gost-bridge*`. Tightening path-routing rules and monitoring persistent, long-lived websocket handshakes can help isolate active tunnels.

---

## 🎯 Conclusion

Sanctuary represents a modern security paradigm: **offensive empathy**. By building, testing, and documenting the precise evasion methods used to carve out persistent enclaves inside serverless environments, we provide Hugging Face with the exact blueprints needed to detect, analyze, and mitigate advanced threat vectors before they can be deployed by real-world adversaries.