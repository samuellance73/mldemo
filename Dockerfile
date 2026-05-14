FROM ubuntu:22.04.
# Install necessary tools
RUN apt-get update && apt-get install -y curl wget sudo

# Install Tailscale
RUN curl -fsSL https://tailscale.com/install.sh | sh

# Install File Browser (Your web-based file manager)
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# Copy our startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Run the script when the container starts
CMD ["/start.sh"]