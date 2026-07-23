"""
title_agent.py
Generates a few title variants per video using fixed patterns (not free-form
LLM guessing), then scores them heuristically. Two patterns are added here
specifically because this is a local shop, not a general content channel:
"location/urgency" and "trust/social proof".
"""
import random

PATTERNS = {
    "question": "{topic}? Here's what you need to know",
    "how_to": "How to fix {topic} — step by step",
    "location_urgency": "{topic} in {location} — same day service",
    "trust": "Why customers trust us for {topic}",
    "curiosity": "The {topic} problem most people ignore",
    "direct_offer": "{topic} — done right, at {shop}",
}

# Patterns intentionally excluded: anything exaggerated/clickbaity conflicts
# with the brand's "never misleading" rule (e.g. "You won't believe...").


def generate_title_variants(topic_title: str, shop_name: str, location: str, n=3) -> list[dict]:
    chosen = random.sample(list(PATTERNS.items()), k=min(n, len(PATTERNS)))
    variants = []
    for label, template in chosen:
        title = template.format(topic=topic_title, location=location, shop=shop_name)
        variants.append({"label": label, "title": title})
    return variants


def score_variant(variant: dict) -> float:
    """
    Placeholder scoring heuristic until real view-data exists.
    Once performance data accumulates in the DB, replace this with a lookup
    of which label (pattern) has historically driven more average views
    (see database.best_performing_categories as the pattern to follow).
    """
    length_score = 1.0 if 20 <= len(variant["title"]) <= 60 else 0.5
    return length_score


def pick_best_variant(variants: list[dict]) -> dict:
    return max(variants, key=score_variant)


if __name__ == "__main__":
    v = generate_title_variants("RAM upgrade for slow laptops", "Your Shop", "Biraul")
    for item in v:
        print(item)
    print("Best:", pick_best_variant(v))
