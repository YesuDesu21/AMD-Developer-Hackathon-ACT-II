#!/bin/bash
set -e

ollama serve &

until ollama list > /dev/null 2>&1; do
    sleep 1
done

# Force the model into memory before the real task loop starts. Without this,
# the first real task pays the cold-load cost (weights disk->RAM), risking a
# timeout against the 30-second-per-response limit on task #1 specifically.
# Best-effort: if the warm-up call itself fails, let main.py proceed anyway
# and take the cold-load hit on its first task rather than crash the container.
ollama run "${LOCAL_MODEL_NAME}" "warm up" > /dev/null 2>&1 || true

exec python main.py
