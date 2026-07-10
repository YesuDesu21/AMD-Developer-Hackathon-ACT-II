def estimate_tokens(text: str) -> int:
    """
    Rough token-count estimate (chars/4 heuristic). No tokenizer dependency
    is installed (requirements.txt only has requests + python-dotenv), and
    the 5 allowed Fireworks models don't share a single tokenizer anyway --
    this is an approximation used only to decide whether to skip a remote
    call, not an exact count.
    """
    return max(1, len(text) // 4)
