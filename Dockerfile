FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---- install Java runtime for TDA (headless) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-21-jre-headless \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (refactored layout)
COPY main.py .
COPY settings.py .
COPY routers ./routers
COPY schemas ./schemas
COPY services ./services

# ---- TDA jar ----
# Keep tda.jar at repo root for reproducible builds.
COPY ./tda.jar /opt/tda/tda.jar

# TDA env (used by app)
ENV TDA_JAR_PATH=/opt/tda/tda.jar \
    TDA_JAVA_BIN=java \
    TDA_MCP_TIMEOUT_SEC=30

EXPOSE 8080

# LLM defaults (Ollama by default; override to openai at runtime)
ENV LLM_PROVIDER=ollama \
    LLM_MODEL=qwen2.5-coder:7b-instruct \
    LLM_TEMP=0.2 \
    OLLAMA_BASE_URL=http://10.2.104.81:11434/v1 \
    OPENAI_API_KEY=ollama

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
