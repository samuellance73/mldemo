---
title: Sanctuary Kasm Workspaces
emoji: 💻
colorFrom: purple
colorTo: pink
sdk: docker
app_port: 6901
pinned: false
---

# Sanctuary Kasm Workspaces 💻

This is a standalone **Kasm Workspaces** deployment providing a containerized desktop environment for the Sanctuary infrastructure.

## 🚀 Deployment Instructions

This project is integrated into the Sanctuary monorepo automation pipeline.

### Prerequisites
Make sure you have your target node configured in `manifests/nodes.yaml`:

```yaml
  kasm:
    hf-repo: "your-username/kasm-space"
    token-env: "HF_TOKEN"
    create-repo: true
    space-sdk: docker
    repo-type: space
    custom-dir: "kasm"
```

### Build & Deploy
Deploy this space using the main repository automation targets:
```bash
make deploy
```

## 🔧 Configuration

Kasm Workspaces provides a full browser-based desktop environment. Configure the following Space Secrets:

- **`VNC_PW`**: VNC password for desktop access (default: "password")
- **`RESOLUTION`**: Desktop resolution (default: "1280x720")

## 📝 Features

- Full browser-based desktop environment
- Support for multiple workspaces and profiles
- Integrated web browser and terminal
- File management and transfer capabilities
- Customizable workspace configurations

> [!NOTE]
> This deployment uses the official Kasm Workspaces Core image and provides a secure, containerized desktop environment accessible via web browser.
