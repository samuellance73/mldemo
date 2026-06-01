---
title: Open WebUI
emoji: 💡
colorFrom: gray
colorTo: blue
sdk: docker
sdk_version: "latest"
pinned: false
---

# Open WebUI Docker Setup

This directory contains the `Dockerfile` for setting up Open WebUI within your project.

## Dockerfile

The `Dockerfile` uses the official `ghcr.io/open-webui/open-webui:main` image as its base. It exposes port `8080`, which is the default port for Open WebUI.

### Building the Docker Image

To build the Docker image, navigate to this directory in your terminal and run:

```bash
docker build -t open-webui .
```

### Running the Docker Container

After building, you can run the Open WebUI container using:

```bash
docker run -d -p 8080:8080 --name open-webui-container open-webui
```

This will start the Open WebUI container in detached mode and map port 8080 of your host to port 8080 of the container.

You can then access Open WebUI in your web browser at `http://localhost:8080`.
