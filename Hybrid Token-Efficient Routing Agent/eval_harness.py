import argparse
import json
import sys
from pathlib import Path

from src.router.policy import Policy
from config.settings import FIREWORKS_API_KEY

DEFAULT_TASKS = [
    {"task_id": "fact_001", "prompt": "What is the capital of France?", "expected": "Paris"},
    {"task_id": "fact_002", "prompt": "What is 17 * 23?", "expected": "391"},
    {"task_id": "fact_003", "prompt": "Who wrote Romeo and Juliet?", "expected": "Shakespeare"},
    {"task_id": "math_001", "prompt": "What is the square root of 289?", "expected": "17"},
    {"task_id": "math_002", "prompt": "If a train travels 60 mph for 2.5 hours, how far does it go?", "expected": "150"},
    {"task_id": "ambig_001", "prompt": "What is the best programming language?", "expected": None},
    {"task_id": "ambig_002", "prompt": "Summarize the plot of a nonexistent movie.", "expected": None},
    {"task_id": "reasoning_001", "prompt": "A farmer has 17 sheep, all but 9 die. How many are left?", "expected": "9"},
    {"task_id": "reasoning_002", "prompt": "What is heavier: a kilogram of feathers or a kilogram of steel?", "expected": "same"},
    {"task_id": "obscure_001", "prompt": "What year did the Lusitania sink?", "expected": "1915"},
]


def check_correct(answer: str, expected: str | None) -> bool | None:
    if expected is None:
        return None
    return str(expected).strip().lower() in answer.strip().lower()


def run_eval(tasks, threshold, dry_run):
    if not FIREWORKS_API_KEY and not dry_run:
        print("WARNING: FIREWORKS_API_KEY not set - remote calls will fail.")

    results = []

    if not dry_run:
        router = Policy()
        router.threshold = threshold

    for task in tasks:
        prompt = task["prompt"]
        task_id = task.get("task_id", "unknown")

        print(f"\n  [{task_id}] {prompt}")
        print(f"  {'-' * 60}")

        if dry_run:
            r = {"answer": "", "model_used": "simulated", "confidence": 0.0, "tokens_used": 0, "escalated": False, "error": None}
        else:
            r = router.route(prompt)
            print(f"  Answer: {r['answer'][:80]}")
            print(f"  Model:  {r['model_used']}")
            print(f"  Conf:   {r['confidence']:.2f}")
            print(f"  Tokens: {r['tokens_used']}")
            if r.get("error"):
                print(f"  Error:  {r['error']}")

        correct = check_correct(r["answer"], task.get("expected"))
        correct_str = "?" if correct is None else ("PASS" if correct else "FAIL")
        print(f"  Result: [{correct_str}]")

        results.append({
            "task_id": task_id,
            "prompt": prompt,
            "expected": task.get("expected"),
            "answer": r["answer"],
            "model_used": r["model_used"],
            "confidence": r["confidence"],
            "tokens_used": r["tokens_used"],
            "correct": correct,
        })

    return results


def run_interactive():
    router = Policy()
    results = []
    task_num = 0

    while True:
        prompt = input("What's on your mind right now?: ").strip()
        if not prompt or prompt.lower() in ("quit", "exit"):
            break

        task_num += 1
        task_id = f"interactive_{task_num:03d}"
        r = router.route(prompt)

        print(f"\n  [{task_id}] {prompt}")
        print(f"  {'-' * 60}")
        print(f"  Answer: {r['answer'][:80]}")
        print(f"  Model:  {r['model_used']}")
        print(f"  Conf:   {r['confidence']:.2f}")
        print(f"  Tokens: {r['tokens_used']}")
        if r.get("error"):
            print(f"  Error:  {r['error']}")

        results.append({
            "task_id": task_id,
            "prompt": prompt,
            "expected": None,
            "answer": r["answer"],
            "model_used": r["model_used"],
            "confidence": r["confidence"],
            "tokens_used": r["tokens_used"],
            "correct": None,
        })

    return results


def print_summary(results):
    graded = [r for r in results if r["correct"] is not None]
    correct = [r for r in graded if r["correct"]]
    total_local = sum(1 for r in results if r["model_used"] == "local")
    total_remote = len(results) - total_local
    total_remote_tokens = sum(r["tokens_used"] for r in results if r["model_used"] != "local")
    accuracy = len(correct) / len(graded) if graded else None

    remote_model_counts = {}
    for r in results:
        if r["model_used"] != "local":
            remote_model_counts[r["model_used"]] = remote_model_counts.get(r["model_used"], 0) + 1

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total tasks:      {len(results)}")
    print(f"  Local answers:    {total_local}")
    print(f"  Remote answers:   {total_remote}")
    for model_name, count in sorted(remote_model_counts.items()):
        print(f"    - {model_name}: {count}")
    print(f"  Remote tokens:    {total_remote_tokens}")
    print(f"  Graded tasks:     {len(graded)}")
    print(f"  Correct:          {len(correct)}")
    print(f"  Accuracy:         {accuracy:.1%}" if accuracy is not None else "  Accuracy:         N/A (no expected values)")
    print(f"{'=' * 70}\n")

    for r in results:
        correct_str = "?" if r["correct"] is None else ("PASS" if r["correct"] else "FAIL")
        print(f"  [{correct_str}] [{r['model_used']:>14}] {r['task_id']}: {r['answer'][:60]}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Batch-evaluate the cascade router")
    parser.add_argument("--tasks", type=str, help="JSON file with task list")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true", help="Skip local/remote calls")
    parser.add_argument("--interactive", action="store_true", help="Prompt for tasks one at a time instead of running a fixed list")
    args = parser.parse_args()

    if args.interactive:
        results = run_interactive()
        print_summary(results)
        return

    if args.tasks:
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    else:
        tasks = DEFAULT_TASKS

    print(f"Running {len(tasks)} tasks (threshold={args.threshold})...")
    results = run_eval(tasks, args.threshold, args.dry_run)
    print_summary(results)


if __name__ == "__main__":
    main()
