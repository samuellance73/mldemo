---
title: Sanctuary Open WebUI
emoji: 🤖
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 7860
pinned: false
---

# Sanctuary Open WebUI 🤖

This is a standalone **Open WebUI** deployment designed to provide a ChatGPT-like interface for the Sanctuary LLM proxy backend.

## 🚀 Deployment Instructions

This project is integrated into the Sanctuary monorepo automation pipeline.

### Prerequisites
Make sure you have your target node configured in `manifests/nodes.yaml`:

```yaml
  openwebui:
    hf-repo: "your-username/openwebui-space"
    token-env: "HF_TOKEN"
    create-repo: true
    space-sdk: docker
    repo-type: space
    custom-dir: "openwebui"
```

### Build & Deploy
Deploy this space using the main repository automation targets:
```bash
make deploy
```

## 🔧 Configuration

Open WebUI connects to the Sanctuary LLM proxy backend. Configure the following Space Secrets:

- **`OPENAI_API_BASE_URL`**: The URL of your LLM proxy endpoint (e.g., `https://server-01.your-space.hf.space/v1/`)
- **`OPENAI_API_KEY`**: Your LLM proxy API key (if required)
- **`WEBUI_SECRET_KEY`**: Secret key for session management (generate a random string)

## 📝 Features

- ChatGPT-like interface for LLM interactions
- Support for multiple LLM providers via the Sanctuary proxy
- Conversation history management
- Code highlighting and syntax support
- Responsive design for web and mobile

> [!NOTE]
> This deployment uses the official Open WebUI Docker image and connects to the Sanctuary LLM proxy service running on backend nodes.
