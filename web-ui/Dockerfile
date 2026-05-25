FROM ghcr.io/open-webui/open-webui:main

# 1. Hugging Face Spaces require the container to listen on Port 7860
ENV PORT=7860
EXPOSE 7860

# 2. Point Open WebUI directly to your LiteLLM gateway
ENV OPENAI_API_BASE_URL=https://samuellance73-mldemo.hf.space/v1
ENV OPENAI_API_KEY=none

# 3. Disable local authentication (using open/unprotected gateway)
ENV WEBUI_AUTH=False

# 4. Inject static security keys so the container never has to write them to disk on boot
ENV WEBUI_SECRET_KEY=sanctuary_covert_vault_secret_key_99
ENV OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=sanctuary_oauth_token_encryption_key_99_secure_bytes

# 5. FIX ALL PERMISSIONS: Switch to root to configure the entire app directory for UID 1000
USER root

# Grant full ownership and write permissions of the entire application directory to the HF user (1000)
RUN mkdir -p /app/backend/data && \
    chown -R 1000:1000 /app && \
    chmod -R 777 /app

# 6. Switch back to the unprivileged Hugging Face user (UID 1000) for execution
USER 1000
