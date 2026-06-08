FROM ghcr.io/open-webui/open-webui:main-slim

# Expose the port Open WebUI runs on
EXPOSE 7860

ENV PORT=7860

# LiteLLM proxy connection (server-01: AlisaAjer/newrepo18)
# OPENAI_API_BASE_URL and OPENAI_API_KEY are the built-in OpenWebUI parameters
# for connecting to any OpenAI-compatible provider.
ENV OPENAI_API_BASE_URL="https://alisaajer-newrepo18.hf.space/v1"
ENV OPENAI_API_KEY="none"
