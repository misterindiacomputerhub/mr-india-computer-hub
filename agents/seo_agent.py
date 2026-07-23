"""
seo_agent.py
Generates SEO description pieces + tags for a topic, then assembles them
into the shop's fixed description template via description_agent.py.
Title comes from title_agent's pattern-based generator (not free-form LLM)
to stay consistent with the brand's anti-clickbait title rules. Uses the
same Groq HTTP pattern as trend_agent.py -- no extra SDK dependency.
"""
import os
import json
import difflib
import requests

from agents import title_agent
from agents import description_agent

from dotenv import load_dotenv
load_dotenv()


SHOP_NAME = os.getenv("SHOP_NAME", "")
SHOP_LOCATION = os.getenv("SHOP_LOCATION", "")
SHOP_CTA = os.getenv("SHOP_CTA", "")


def _load_services():
    with open("data/services.json") as f:
        data = json.load(f)
    flat = []
    for cat in data["categories"]:
        for topic in cat["topics"]:
            flat.append({"category": cat["category"], "title_seed": topic["title_seed"], "id": topic["id"]})
    return flat


def match_real_service(topic_title: str, keyword: str = "") -> dict:
    """
    Matches a trending topic against the shop's real service list (text
    similarity, no extra API call) so SEO/tags/clip prompts always point at
    something the shop genuinely offers, not a generic guess.
    """
    services = _load_services()
    query = f"{topic_title} {keyword}".lower()

    best, best_score = None, 0.0
    for svc in services:
        candidate = f"{svc['category']} {svc['title_seed']}".lower()
        score = difflib.SequenceMatcher(None, query, candidate).ratio()
        if score > best_score:
            best_score, best = score, svc

    return best or services[0]


SEO_SYSTEM_PROMPT_TEMPLATE = """You write YouTube Shorts description content for {shop_name},
a local computer & mobile repair shop's Shorts channel in {location}. Given a
video title and the shop's REAL matching service, write the RAW PIECES of a
description (the final layout is assembled separately -- you just supply
the content) plus tags.

The video is genuinely about this real service the shop offers:
Category: {category}
Service: {service_title}

Rules:
- "hook": 1 line, attention-grabbing, clearly about the real service above.
- "features": 4-8 short bullet phrases (2-6 words each), concrete and
  specific to this service -- not vague filler.
- "audience_line": 1 line on who this is for / why it matters.
- Never claim things not confirmed (no fake certifications, no guaranteed
  results, no invented prices, no fake testimonials).
- "tags": 8-12 tags, no '#' symbol, mix of the real category/service name
  and the actual trending search term "{keyword}" -- do not invent unrelated
  generic tags.
- Return ONLY valid JSON, no markdown fences, no preamble.
Schema: {{"hook": str, "features": [str, ...], "audience_line": str, "tags": [str, ...]}}
"""


def generate_seo(topic_title: str, keyword: str = "") -> dict:
    matched = match_real_service(topic_title, keyword)

    variants = title_agent.generate_title_variants(topic_title, SHOP_NAME, SHOP_LOCATION)
    best = title_agent.pick_best_variant(variants)
    title = best["title"]

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY to use SEO generation.")

    system_prompt = SEO_SYSTEM_PROMPT_TEMPLATE.format(
        shop_name=SHOP_NAME, location=SHOP_LOCATION,
        category=matched["category"], service_title=matched["title_seed"], keyword=keyword,
    )

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Video title: {title}\nTopic: {topic_title}"},
            ],
            "temperature": 0.6,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    raw = raw.strip("`").removeprefix("json").strip()
    data = json.loads(raw)

    description = description_agent.generate_description(
        hook=data["hook"],
        features=data["features"],
        audience_line=data["audience_line"],
        tags=data["tags"],
    )

    return {"title": title, "description": description, "tags": data["tags"], "matched_service": matched}


def generate_seo_checked(topic_title: str, keyword: str = "") -> dict:
    """
    Same as generate_seo(), but runs the description through the same
    compliance filter script_agent.py uses on scripts. Raises if a banned
    claim slips through, so the caller can surface it instead of publishing.
    """
    from agents import script_agent

    result = generate_seo(topic_title, keyword)
    passed, violations = script_agent.compliance_check(result["description"])
    if not passed:
        raise ValueError(f"SEO description blocked by compliance filter: {violations}")
    return result
