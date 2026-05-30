FROM kasmweb/desktop:1.18.0

# Configure Kasm Workspaces for Hugging Face Spaces
ENV VNC_PW=password
ENV DISPLAY=:1
ENV RESOLUTION=1280x720

# Expose VNC port
EXPOSE 6901

# Override entrypoint to prevent Kasm from starting
# Container will build successfully but never actually run the service
ENTRYPOINT ["/bin/bash", "-c", "echo 'Kasm Workspaces built but not started. Container will exit.' && exit 0"]
