import argparse
import json
import sys
from pathlib import Path

from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.policy import should_escalate
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
    local_client = LocalClient()
    remote_client = RemoteClient()

    if not FIREWORKS_API_KEY and not dry_run:
        print("WARNING: FIREWORKS_API_KEY not set - remote calls will fail.")

    results = []
    total_local = 0
    total_remote = 0
    total_remote_tokens = 0

    for task in tasks:
        prompt = task["prompt"]
        task_id = task.get("task_id", "unknown")

        print(f"\n  [{task_id}] {prompt}")
        print(f"  {'-' * 60}")

        if dry_run:
            print(f"  Dry-run: skipping local/remote calls")
            model_used = "simulated"
            answer = ""
            tokens_used = 0
            confidence = 0.0
        else:
            local_result = local_client.run_local(prompt)
            local_answer = local_result.get("answer", "")
            confidence = local_result.get("confidence", 0.0)

            print(f"  Local:  {local_answer[:80]}")
            print(f"  Conf:   {confidence:.2f}")

            if not should_escalate(local_result, threshold):
                answer = local_answer
                model_used = "local"
                tokens_used = 0
                total_local += 1
                print(f"  [KEPT] Local answer accepted")
            else:
                remote_result = remote_client.generate(prompt)
                answer = remote_result.get("answer", "")
                model_used = remote_result.get("model", "remote")
                tokens_used = remote_result.get("tokens_used", 0)
                total_remote += 1
                total_remote_tokens += tokens_used
                error = remote_result.get("error")
                if error:
                    print(f"  [ERROR] Remote error: {error}")
                else:
                    print(f"  Remote: {answer[:80]}")
                    print(f"  Tokens: {tokens_used}")

        correct = check_correct(answer, task.get("expected"))
        correct_str = "?" if correct is None else ("PASS" if correct else "FAIL")
        print(f"  Result: [{correct_str}]")

        results.append({
            "task_id": task_id,
            "prompt": prompt,
            "expected": task.get("expected"),
            "answer": answer,
            "model_used": model_used,
            "confidence": confidence,
            "tokens_used": tokens_used,
            "correct": correct,
        })

    return results, total_local, total_remote, total_remote_tokens


def print_summary(results, total_local, total_remote, total_remote_tokens):
    graded = [r for r in results if r["correct"] is not None]
    correct = [r for r in graded if r["correct"]]
    accuracy = len(correct) / len(graded) if graded else None

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total tasks:      {len(results)}")
    print(f"  Local answers:    {total_local}")
    print(f"  Remote answers:   {total_remote}")
    print(f"  Remote tokens:    {total_remote_tokens}")
    print(f"  Graded tasks:     {len(graded)}")
    print(f"  Correct:          {len(correct)}")
    print(f"  Accuracy:         {accuracy:.1%}" if accuracy is not None else "  Accuracy:         N/A (no expected values)")
    print(f"{'=' * 70}\n")

    for r in results:
        correct_str = "?" if r["correct"] is None else ("PASS" if r["correct"] else "FAIL")
        print(f"  [{correct_str}] [{r['model_used']:>6}] {r['task_id']}: {r['answer'][:60]}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Batch-evaluate the cascade router")
    parser.add_argument("--tasks", type=str, help="JSON file with task list")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true", help="Skip remote calls, just show what would escalate")
    args = parser.parse_args()

    if args.tasks:
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    else:
        tasks = DEFAULT_TASKS

    print(f"Running {len(tasks)} tasks (threshold={args.threshold})...")
    results, total_local, total_remote, total_remote_tokens = run_eval(tasks, args.threshold, args.dry_run)
    print_summary(results, total_local, total_remote, total_remote_tokens)


if __name__ == "__main__":
    main()
