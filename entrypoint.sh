#!/bin/bash
set -e

ollama serve &

until ollama list > /dev/null 2>&1; do
    sleep 1
done

exec python main.py
