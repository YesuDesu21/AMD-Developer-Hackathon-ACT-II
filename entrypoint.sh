#!/bin/bash
set -e

ollama serve &

until ollama list > /dev/null 2>&1; do
    sleep 1
done

ollama pull "${LOCAL_MODEL_NAME:-gemma2:9b}"

exec python main.py
