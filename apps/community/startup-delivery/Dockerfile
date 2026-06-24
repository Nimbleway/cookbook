# The Python agent bridge (FastAPI) for Fly.io. The web (SvelteKit) deploys
# separately to Vercel and proxies here via AGENT_URL. Only the bridge's deps are
# installed: tower/pyarrow are NOT on the import path of agent.server.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    DELIVERIES_LOG=/data/deliveries.jsonl

WORKDIR /app

COPY agent/requirements.txt ./agent/requirements.txt
RUN pip install -r agent/requirements.txt

COPY agent ./agent

EXPOSE 8080

# Honors $PORT (Fly sets it); binds all interfaces.
CMD ["sh", "-c", "uvicorn agent.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
