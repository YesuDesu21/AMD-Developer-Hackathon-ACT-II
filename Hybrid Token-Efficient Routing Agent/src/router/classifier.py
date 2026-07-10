import re

CODE_KEYWORDS = [
    "code", "function", "debug", "bug", "compile", "syntax",
    "algorithm", "python", "javascript", "class ", "def ", "error:",
]

MATH_KEYWORDS = [
    "calculate", "compute", "solve", "equation", "sum of",
    "how many", "how much",
]

REASONING_KEYWORDS = [
    "why", "explain", "prove", "infer", "logic", "if and only if",
    "therefore", "cause", "premise",
]

CREATIVE_KEYWORDS = [
    "write a", "poem", "story", "imagine", "compose", "creative",
    "write me", "draft", "brainstorm",
]

FACTUAL_QA_KEYWORDS = [
    "what is", "who is", "when did", "where is", "capital of", "define",
    "convert", "definition", "meaning", "what does", "how to",
    "is a", "are the", "difference between", "list", "name the",
]

MATH_PATTERN = re.compile(r"\d+\s*[\+\-\*/]\s*\d+")
CONVERSION_PATTERN = re.compile(r"\d+\s*(mph|kph|km|mi|lbs|kg|°f|°c|celsius|fahrenheit|miles|kilometers|pounds|kilograms)")

CATEGORY_KEYWORDS = [
    ("code", CODE_KEYWORDS),
    ("math", MATH_KEYWORDS),
    ("reasoning", REASONING_KEYWORDS),
    ("creative", CREATIVE_KEYWORDS),
    ("factual_qa", FACTUAL_QA_KEYWORDS),
]


def classify_task(prompt: str) -> str:
    """
    Heuristic keyword-scoring classifier (same style as complexity.py's
    complexity_checker). Returns the category with the most keyword hits, or
    "general" if nothing matches. A numeric expression like "17 * 23" is a
    strong enough signal to short-circuit straight to "math".
    """
    text = prompt.lower().strip()

    if MATH_PATTERN.search(text):
        return "math"

    if CONVERSION_PATTERN.search(text):
        return "factual_qa"

    best_category = "general"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category
