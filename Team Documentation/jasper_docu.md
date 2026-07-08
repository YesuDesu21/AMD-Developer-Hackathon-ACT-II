
# Jasper's Documentation

---
## Notes to teammates

Policy expects:
- local_client.generate(task: dict) -> str
- remote_client.generate(task: dict) -> str
- logger.log(task_id, model, tokens, confidence, latency)


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

---

```mermaid
graph TD
    User([Incoming User Query]) --> Main[main.py]
    Main --> Policy[src/router/policy.py]
    
    %% Optional Path
    Policy -.->|Optional Check: Prompt too heavy| RemoteClient[src/models/remote_client.py]
    
    %% Standard Path
    Policy -->|Step 1: Free Request| LocalClient[src/models/local_client.py]
    LocalClient -->|Execute llama3.2:1b| LocalOutput[Local Ollama Result]
    LocalOutput --> Policy
    
    %% Validation
    Policy -->|Step 2: Inspect Output| Validators[src/router/validators.py]
    Validators -->|Validation Check| IsValid{Is Output Valid?}
    
    %% Branching Decisions
    IsValid -->|True| ReturnLocal[Return Local Text]
    IsValid -->|False| RemoteClient
    
    %% Remote Execution Flow
    RemoteClient -->|Execute deepseek-v4-pro| CloudOutput[Cloud DeepSeek Result]
    CloudOutput --> Logger[src/utils/logger.py]
    Logger -->|Calculate Token Savings| ReturnCloud[Return Cloud Text]
    
    ReturnLocal --> Done([Done! Output Delivered])
    ReturnCloud --> Done

