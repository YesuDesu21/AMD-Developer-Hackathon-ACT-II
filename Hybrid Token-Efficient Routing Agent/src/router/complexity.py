ANALYTICAL = [
    "analyze", "analysis", "critique", "evaluate", "examine",
    "investigate", "inspect", "diagnose", "assess", "appraise",
    "interpret", "justify", "reason", "rationale",
]

CREATIVE = [
    "write", "create", "design", "develop", "compose",
    "draft", "formulate", "generate", "produce", "construct",
    "build", "implement", "author", "craft", "devise",
]

COMPARATIVE = [
    "compare", "contrast", "differentiate", "distinguish",
    "similarities", "differences", "versus", "vs",
    "relative", "opposing", "alternative", "trade-off",
    "pros and cons", "advantages", "disadvantages",
]

EXPLANATORY = [
    "explain", "describe", "elaborate", "illustrate",
    "demonstrate", "clarify", "elucidate", "expound",
    "in detail", "thoroughly", "comprehensively",
    "break down", "walk through",
]

MULTI_STEP_REASONING = [
    "calculate", "compute", "solve", "derive", "prove",
    "determine", "figure out", "work out", "find out",
    "deduce", "infer", "extrapolate", "approximate",
    "solve for", "find x", "what is the value",
]

SYNTHESIS = [
    "synthesize", "synthesis", "integrate", "combine",
    "merge", "unify", "consolidate", "aggregate",
    "amalgamate", "coalesce",
]

HYPOTHETICAL = [
    "hypothetical", "hypothetically", "suppose", "imagine",
    "assume", "speculate", "what if", "what would",
    "could it be", "is it possible", "would happen",
    "thought experiment",
]

DOMAIN_SPECIFIC = [
    "algorithm", "function", "equation", "formula",
    "theorem", "proof", "hypothesis", "theory",
    "theoretical", "abstract", "concept", "paradigm",
    "code", "program", "compile", "debug", "optimize",
    "neural", "network", "machine learning", "deep learning",
    "architecture", "framework", "system design",
]

PLANNING = [
    "plan", "strategy", "approach", "methodology",
    "framework", "system", "architecture", "workflow",
    "pipeline", "roadmap", "blueprint", "outline",
    "step by step", "procedure", "protocol",
]

LOGICAL_REASONING = [
    "cause", "effect", "implication", "inference",
    "premise", "argument", "conclusion", "logical",
    "conditional", "if and only if", "necessary",
    "sufficient", "contradiction", "paradox",
]

QUANTITATIVE = [
    "how many", "how much", "what percentage", "what fraction",
    "ratio", "proportion", "rate", "frequency", "probability",
    "statistics", "statistical", "correlation", "causation",
    "distribution", "variance", "standard deviation",
]

TEMPORAL_SEQUENTIAL = [
    "sequence", "order", "timeline", "chronology",
    "chronological", "subsequent", "subsequently",
    "previous", "prior", "following", "initial",
    "consecutive", "simultaneous", "succeeding",
    "firstly", "secondly", "finally", "meanwhile",
    "thereafter", "hitherto", "then", "after",
]

CONNECTIVES = [
    "however", "therefore", "consequently", "furthermore",
    "moreover", "nevertheless", "nonetheless", "notwithstanding",
    "whereas", "although", "despite", "hence", "thus",
    "accordingly", "additionally", "alternatively",
]

MATHEMATICAL_PATTERNS = [
    r"\d+\s*[\+\-\*\/]\s*\d+", r"=", r"equation",
    r"formula", r"calculate", r"compute",
]


def complexity_checker(task: str) -> float:
    text = task.lower().strip()
    score = 0.0
    matched_categories = set()

    word_count = len(text.split())
    if word_count > 15:
        score += 0.1
    if word_count > 25:
        score += 0.1
    if word_count > 40:
        score += 0.1

    categories = [
        ("analytical", ANALYTICAL, 0.15),
        ("creative", CREATIVE, 0.15),
        ("comparative", COMPARATIVE, 0.15),
        ("explanatory", EXPLANATORY, 0.12),
        ("reasoning", MULTI_STEP_REASONING, 0.15),
        ("synthesis", SYNTHESIS, 0.2),
        ("hypothetical", HYPOTHETICAL, 0.15),
        ("domain_specific", DOMAIN_SPECIFIC, 0.15),
        ("planning", PLANNING, 0.15),
        ("logical", LOGICAL_REASONING, 0.12),
        ("quantitative", QUANTITATIVE, 0.12),
        ("temporal", TEMPORAL_SEQUENTIAL, 0.08),
        ("connectives", CONNECTIVES, 0.08),
    ]

    for cat_name, keywords, weight in categories:
        for kw in keywords:
            if kw in text:
                score += weight
                matched_categories.add(cat_name)
                break

    category_bonus = max(0, (len(matched_categories) - 1)) * 0.1
    score += category_bonus

    if text.count("?") >= 2:
        score += 0.1

    if len(text) > 200:
        score += 0.1

    return min(score, 1.0)
