# Pinned so the resulting image always gets a linux/amd64 manifest, even if
# built on an Apple Silicon / ARM dev machine that doesn't pass --platform.
FROM --platform=linux/amd64 python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ["TokenGate/", "."]

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OLLAMA_HOST=http://localhost:11434
ARG LOCAL_MODEL_NAME=gemma2:2b
ENV LOCAL_MODEL_NAME=${LOCAL_MODEL_NAME}

# Bake model weights into the image at build time: the grading VM has no
# Ollama/runtime pre-installed and no budget for a network pull at container
# startup, so the weights must already be on disk when the container boots.
RUN ollama serve > /tmp/ollama-build.log 2>&1 & \
    OLLAMA_PID=$! && \
    until ollama list > /dev/null 2>&1; do sleep 1; done && \
    ollama pull "${LOCAL_MODEL_NAME}" && \
    kill "${OLLAMA_PID}"

ENTRYPOINT ["/entrypoint.sh"]
