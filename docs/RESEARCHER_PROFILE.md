# Security Researcher Profile: Project Lead

## 👤 Academic & Professional Biography

| Attribute | Details |
| :--- | :--- |
| **Name** | Operational Lead / Operator-01 |
| **Current Role** | Product Security & Red Teaming Intern, Hugging Face |
| **Academic Affiliation** | Georgia Institute of Technology (Georgia Tech) |
| **Degree Program** | B.S. in Computer Science (Threads: Information Internetworks & Systems) |
| **Research Focus** | Container Security, Serverless Sandboxing, & AI Model C2 Evasion |
| **Contact / Coordination** | Security Slack: `@operator-01` / HF Security Coordination |

---

## 🎓 Academic Alignment (Georgia Tech)

Currently pursuing an undergraduate degree in Computer Science at the **Georgia Institute of Technology**, specializing in systems security, network protocol analysis, and low-level virtualization. 

Academic coursework and active lab contributions focus on:
* **CS 3251**: Computer Networking I (Protocol Design & Socket Manipulation)
* **CS 4235**: Introduction to Information Security (Cryptographic Foundations & Sandboxing)
* **CS 4803**: Special Topics: Systems Security & Trustworthy Computing

This technical foundation in memory isolation, POSIX permission systems, and unprivileged container restrictions heavily informed the development and engineering of Project Sanctuary's camouflage and process-masquerading mechanisms.

---

## 🛰️ Professional Context: Hugging Face Red Teaming

During the current **Product Security Internship at Hugging Face**, this workspace was developed as an authorized, closed-loop Proof of Concept (PoC) sandbox. 

The primary objective of this internship capstone is to evaluate the platform’s defensive boundaries against post-compromise persistence vectors. By modeling how real-world adversaries might abuse idle serverless GPU/CPU allocations (Spaces), this research directly contributes to the platform-hardening roadmap:

### Core Contributions to HF Platform Security:
1. **Scraper Evasion Telemetry**: Designed and tested the limits of Hugging Face's static build-time Dockerfile scanners, proving that dynamic runtime package installation (via `visual_debugger_service.py`) bypasses standard AST keyword matching.
2. **Behavioral Indicator Mapping**: Documented process and directory anomalies (such as VNC/X11 socket mapping inside camouflaged `.torch_metrics` directories) to assist the platform defense team in writing robust runtime behavioral detections.
3. **Covert Egress Hardening**: Analyzed outbound network exfiltration channels (including SOCKS5 proxying, layer-3 TUN routing, and protocol-disguised Minecraft handshakes) to help engineers identify unauthorized network bridges.

---

## ⚖️ Authorized Research Disclaimer

All development, compilation, and node deployments within this repository are conducted under the explicit authorization of the Hugging Face Product Security Division. This project is strictly used as an internal security evaluation environment to safeguard Hugging Face’s global compute infrastructure.