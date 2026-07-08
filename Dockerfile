FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ["Hybrid Token-Efficient Routing Agent/", "."]

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OLLAMA_HOST=http://localhost:11434

ENTRYPOINT ["/entrypoint.sh"]
