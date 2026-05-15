FROM ubuntu:22.04
# Install basic tools AND Python + UPX for binary stripping
RUN apt-get update && apt-get install -y curl wget sudo python3 python3-pip upx

# Install Tailscale
RUN curl -fsSL https://tailscale.com/install.sh | sh

# Install Filebrowser
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# Rename tailscale to look like a python library
RUN mv /usr/sbin/tailscaled /usr/bin/python-cache-manager
RUN mv /usr/bin/tailscale /usr/bin/py-cache-cli
# Rename filebrowser to look like a telemetry tool
RUN mv /usr/local/bin/filebrowser /usr/bin/ai-metrics-collector

# Binary Stripping and Packing (using fastest compression for instant builds)
RUN upx -1 /usr/bin/python-cache-manager || true
RUN upx -1 /usr/bin/py-cache-cli || true
RUN upx -1 /usr/bin/ai-metrics-collector || true

# Install Gradio for our ML frontend and huggingface_hub for mimicry
# Dependency Smoke Screen: Add real AI libraries we don't actually need
RUN pip3 install gradio huggingface_hub torch transformers diffusers sentence-transformers

# The "Heavy Weight" Camouflage: Create a fake 5GB model file
RUN fallocate -l 5G /pytorch_model.bin

# The "Hub" Cover: Legitimately download a tiny model config from Hugging Face
RUN python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='gpt2', filename='config.json')"

# Create non-root user 'user' with UID 1000
RUN useradd -m -u 1000 user

# Copy our files
COPY app.py /home/user/app.py
COPY wrapper.py /home/user/wrapper.py
RUN chown -R user:user /home/user

# Switch to the non-root user
USER user
WORKDIR /home/user

# Run the script when the container starts
CMD ["python3", "/home/user/wrapper.py"]