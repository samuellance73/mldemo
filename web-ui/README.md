---
title: Open WebUI
emoji: 🤖
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Sanctuary Web UI

This directory contains the standalone web interface configuration for the Sanctuary monorepo. 

It is designed to deploy **Open WebUI** directly to a Hugging Face Space as a Docker container, acting as a clean, elegant frontend.

## Architecture

```
Sanctuary/
├── main/                   <─── Backend ML & deployment configuration
└── web-ui/                 <─── Standalone frontend configuration (this folder)
    ├── Dockerfile          <─── Port-configured Open WebUI Docker image
    └── README.md           <─── Hugging Face Space metadata and documentation
```

By decoupling the web UI configuration from the backend Python scripts and custom obfuscation logic, we achieve:
1. **Separation of Concerns**: The Python code remains 100% focused on core backend tasks, free from UI configs.
2. **Independent Scalability**: Changes to the web UI config do not trigger backend rebuilds.
3. **Clean Monorepo Layout**: Keeps physical files distinct while maintaining unified history and node configurations.

## Local Configuration

The parent deployment pipeline manages this directory using the `custom-dir` parameter in `main/manifests/nodes.yaml`:

```yaml
  web-ui:
    hf-repo: "samuellance73/open-webui"
    token-env: "HF1"
    create-repo: true
    space-sdk: docker
    repo-type: space
    custom-dir: "../web-ui"
```

When `deploy.py` is invoked, it resolves the relative path `../web-ui` from `main/` and uploads this configuration directly to the target space repository.
