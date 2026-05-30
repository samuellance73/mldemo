FROM tailscale/tailscale:latest AS tailscale

FROM ghcr.io/open-webui/open-webui:main

# Copy Tailscale binaries from the tailscale image
COPY --from=tailscale /usr/local/bin/tailscale /usr/local/bin/tailscale
COPY --from=tailscale /usr/local/bin/tailscaled /usr/local/bin/tailscaled

# Configure Tailscale for userspace networking mode
ENV TS_STATE_DIR=/var/lib/tailscale
ENV TS_SOCKET=/var/run/tailscale/tailscaled.sock
ENV TS_USERSPACE_NETWORKING=true

# Create necessary directories for Tailscale
RUN mkdir -p /var/lib/tailscale /var/run/tailscale

# Configure Open WebUI to listen on port 7860 for Hugging Face Spaces
ENV PORT=7860
ENV HOST=0.0.0.0

# Configure to connect to the llm_proxy service from main deployment
# This will be set via Space Secret or environment variable
ENV OPENAI_API_BASE_URL=""
ENV OPENAI_API_KEY=""

# Enable authentication (set via Space Secret)
ENV WEBUI_AUTH="True"
ENV WEBUI_SECRET_KEY=""

# Disable default models since we'll use the llm_proxy backend
ENV ENABLE_OPENAI_API="True"

# Expose ports
EXPOSE 7860
EXPOSE 41641/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:7860/health || exit 1

# Start script to run both services
COPY start.sh /start.sh
RUN chmod +x /start.sh
ENTRYPOINT ["/start.sh"]
