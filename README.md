# Sanctuary 🌌

> *"We are creating a world that all may enter without privilege or prejudice accorded by race, economic power, military force, or station of birth... a world where anyone, anywhere may express his or her beliefs, no matter how singular, without fear of being coerced into silence or conformity."*
> — John Perry Barlow, *A Declaration of the Independence of Cyberspace* (1996)

---

Welcome to the **Sanctuary** workspace—an authorized, highly sophisticated security evaluation and threat emulation platform built for Hugging Face Spaces. 

## 📚 Technical Documentation Hub

To gain full context on how this entire monorepo is structured, designed, compiled, and operated, please refer to our curated documentation guides:

1. **[Architectural & Technical Guide](file:///home/trueking/Safe/Proj/Hug/Sanctuary/docs/ARCHITECTURAL_GUIDE.md)** 📖
   * *A premium, comprehensive deep-dive into the entire ecosystem's code architecture, process lifecycles, compilation/evasion pipeline, VNC headless graphical debugger, private tunneling stack, and administrative control backdoors.*
2. **[Threat Simulation Brief (CONTEXT.md)](file:///home/trueking/Safe/Proj/Hug/Sanctuary/docs/CONTEXT.md)** 🛰️
   * *High-level overview of our evasions, process masquerading mappings, model weight buffer pre-allocations, and active post-exploitation simulation tools.*
3. **[Academic Justification & Profile (RESEARCHER_PROFILE.md)](file:///home/trueking/Safe/Proj/Hug/Sanctuary/docs/RESEARCHER_PROFILE.md)** 🔬
   * *Academic biographies, professional affiliations, threat modeling theory, MITRE ATT&CK mappings, and legal authorization statements.*

---

## 🛠️ Monorepo Quick-Reference

* **`main/Dockerfile`**: camouflaged Ubuntu-based environment setup with binary compression, process masquerades, and headless display sockets.
* **`main/scripts/build.py`**: Local compiler that compiles Python to raw bytecode (`.pyc`), strips source code (`.py`), minifies files, and reverses AST string identifiers (`harden`).
* **`scripts/deploy.py`**: CLI deployer that synchronizes node manifests, pushes obfuscated space secrets, and pushes bytecode bundles to target spaces.
* **`scripts/cc.py`**: Administrative client CLI manager used to open local port forwards and shell connections using Chisel, GOST, Tailscale, or Playit tunnels.
