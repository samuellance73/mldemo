---
title: Sanctuary Workspace
emoji: 🌌
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Sanctuary Workspace 🌌

This is a standalone, custom-configured **Kasm Workspaces Container** designed to deploy directly to Hugging Face Spaces.

## 🚀 Deployment Instructions

This project is integrated into the Sanctuary monorepo automation pipeline.

### Prerequisites
Make sure you have your target node configured in `main/manifests/nodes.yaml`:

```yaml
  kasm-desktop:
    hf-repo: "your-username/kasm-desktop-space"
    token-env: "HF_TOKEN"
    create-repo: true
    space-sdk: docker
    repo-type: space
    custom-dir: "kasm-workspace"
```

### Build & Deploy
Deploy this space using the main repository automation targets:
```bash
make deploy
```

## 🔐 Authentication
By default, the container sets a fallback password:
*   **Username:** `kasm_user`
*   **Password:** `password`

> [!WARNING]
> It is highly recommended to override the default password. You can set the **`VNC_PW`** space secret in your Hugging Face Space settings to configure a custom secure password.
