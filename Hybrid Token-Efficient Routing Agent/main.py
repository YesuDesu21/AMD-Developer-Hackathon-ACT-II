import json
import sys
from pathlib import Path

from src.router.policy import Policy

INPUT_PATH = Path("/input/tasks.json")
OUTPUT_PATH = Path("/output/results.json")


def load_tasks(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_results(path: Path, results: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f)


def run_task(router: Policy, task: dict) -> dict:
    task_id = task.get("task_id", "unknown") if isinstance(task, dict) else "unknown"
    try:
        prompt = task.get("prompt", "")
        outcome = router.route(prompt)
        answer = outcome.get("answer", "")
    except Exception as exc:
        print(f"[main] task {task_id} failed: {exc}", file=sys.stderr)
        answer = ""
    return {"task_id": task_id, "answer": answer}


def main() -> int:
    try:
        tasks = load_tasks(INPUT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[main] could not read {INPUT_PATH}: {exc}", file=sys.stderr)
        return 1

    router = Policy()
    results = [run_task(router, task) for task in tasks]

    try:
        write_results(OUTPUT_PATH, results)
    except OSError as exc:
        print(f"[main] could not write {OUTPUT_PATH}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
