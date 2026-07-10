import sys
sys.path.insert(0, ".")
from src.router.policy import Policy

router = Policy()

# Test 1: Easy factual question (should use local)
r1 = router.route("What is the capital of the Philippines?")
print(f"Test 1 - Capital of Philippines:")
print(f"  Model: {r1['model']}, Answer: {r1['answer'][:60]}")

# Test 2: Easy math (should use local)
r2 = router.route("What is the square root of 144?")
print(f"\nTest 2 - Square root of 144:")
print(f"  Model: {r2['model']}, Answer: {r2['answer'][:60]}")

# Test 3: Creative task (should use remote, complete answer)
r3 = router.route("What is the most popular Bible verse?")
print(f"\nTest 3 - Popular Bible verse:")
print(f"  Model: {r3['model']}, Answer: {r3['answer'][:120]}...")
print(f"  Answer length: {len(r3['answer'])} chars")

# Test 4: Long creative (should use remote, complete answer)
r4 = router.route("Write a 200-word post-mortem about why a customer churn ML model failed due to data drift.")
print(f"\nTest 4 - 200-word post-mortem:")
print(f"  Model: {r4['model']}, Tokens: {r4['tokens_used']}")
print(f"  Answer length: {len(r4['answer'])} chars")
print(f"  Last 80 chars: ...{r4['answer'][-80:]}")
