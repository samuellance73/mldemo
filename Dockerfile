FROM ubuntu:22.04
# Install basic tools AND Python
RUN apt-get update && apt-get install -y curl wget sudo python3 python3-pip

# Install Tailscale
RUN curl -fsSL https://tailscale.com/install.sh | sh

# Install Gradio for our ML frontend
RUN pip3 install gradio

# Copy our files
COPY app.py /app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Run the script when the container starts
CMD ["/start.sh"]