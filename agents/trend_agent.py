"""
trend_agent.py
Suggests likely-trending, relevant topics for the shop's niche using the
same Groq LLM already configured for script_agent. No live trend data —
these are LLM best-guesses based on common seasonal/recurring patterns in
computer & mobile repair services in India.
"""
import os
import json
import requests

SHOP_LOCATION = os.getenv("SHOP_LOCATION", "")

TREND_SYSTEM_PROMPT = """You suggest short-video topic ideas for a local computer &
mobile repair shop's YouTube Shorts channel in India. Suggest topics that are
LIKELY to be currently relevant — seasonal issues (e.g. monsoon moisture damage,
summer overheating), common recurring problems, back-to-school laptop needs,
festival-season device prep, etc. Do not invent specific news events or claim
real-time knowledge; base suggestions on well-known recurring patterns only.

Return ONLY a JSON array of 5 objects, no markdown, no preamble, in this exact shape:
[
  {"title_seed": "short topic phrase", "category": "short category name", "angle": "tip"}
]
angle must be one of: tip, explainer, govt_guide, product_review, showcase
"""


def suggest_trending_topics(n: int = 5) -> list[dict]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY to use trend suggestions.")

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": TREND_SYSTEM_PROMPT},
                {"role": "user", "content": f"Suggest {n} topics for a shop in {SHOP_LOCATION}."},
            ],
            "temperature": 0.8,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    raw = raw.strip("`").removeprefix("json").strip()
    return json.loads(raw)
