
# Jasper's Documentation
---
## File structure:

```
AMD-Developer-Hackathon-ACT-II/
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Holds thresholds, model names, API keys
│
├── src/
│   ├── __init__.py
│   │
│   ├── router/              <-- YOUR MAIN DOMAIN
│   │   ├── __init__.py
│   │   ├── policy.py        # Core escalation logic (threshold checks)
│   │   └── validators.py    # Regex, schema, and structural format checks
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── local_client.py  # (Local Ops teammate) Ollama connector & prompt template
│   │   └── remote_client.py # (Fireworks teammate) API connector & token tracker
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py        # (Eval teammate) Logs task_id, model used, tokens, confidence
│
├── tests/
│   ├── test_router.py       # Unit tests for your decision logic
│   └── placeholder_tasks.json
│
├── main.py                  # The orchestrator tying src/ modules together
├── eval_harness.py          # Runs batch tests to calculate accuracy vs token cost
├── Dockerfile               # Packages everything for submission
├── requirements.txt         # Python dependencies
└── README.md
```