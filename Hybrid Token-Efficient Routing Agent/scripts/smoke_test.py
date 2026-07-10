"""Manual dev sanity check for the router. Not part of the submission entrypoint.

Run locally with: python scripts/smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.policy import Policy


def main() -> None:
    router = Policy()
    result = router.route("What is the capital of France?")
    print(f"Answer:     {result['answer']}")
    print(f"Model:      {result['model']}")
    print(f"Model Name: {result['model_name']}")
    print(f"Conf:       {result['confidence']:.2f}")
    print(f"Tokens:     {result['tokens_used']}")


if __name__ == "__main__":
    main()
