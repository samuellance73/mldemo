FROM kasmweb/ubuntu-jammy-desktop:1.17.0

USER root

# Install socat for port forwarding
RUN apt-get update && apt-get install -y socat && rm -rf /var/lib/apt/lists/*

# Disable SSL requirement in the system-wide KasmVNC configuration so it works with HF Spaces HTTP routing
RUN if [ -f /etc/kasmvnc/kasmvnc.yaml ]; then \
        sed -i 's/require_ssl: true/require_ssl: false/g' /etc/kasmvnc/kasmvnc.yaml; \
    fi

# Configure default VNC password (can be overridden via Hugging Face Space secrets or env vars)
ENV VNC_PW=password

# Copy the custom startup script to handle port forwarding to 7860
COPY custom_startup.sh /dockerstartup/custom_startup.sh
RUN chmod +x /dockerstartup/custom_startup.sh && chown 1000:0 /dockerstartup/custom_startup.sh

# Ensure home directory permissions are clean
RUN chown -R 1000:0 /home/kasm-default-profile

USER 1000
