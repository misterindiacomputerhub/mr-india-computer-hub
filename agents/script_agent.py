"""
script_agent.py
Turns one content-queue topic into a short video script.
Brand-voice and compliance rules are a FIXED system prompt — never left to the
LLM's discretion per-video, since a wrong claim from a local shop is a real
trust/legal risk, not just a bad take.
"""
import os
import json
import requests

SHOP_NAME = os.getenv("SHOP_NAME", "Your Shop Name")
SHOP_LOCATION = os.getenv("SHOP_LOCATION", "")
SHOP_CTA = os.getenv("SHOP_CTA", "Visit us or call to book.")

SYSTEM_PROMPT = f"""You write short (60-90 second) YouTube Shorts / video scripts for a local
computer & services shop called {SHOP_NAME} in {SHOP_LOCATION}.

LANGUAGE: Write the ENTIRE script in natural, spoken Hindi using Devanagari script
(e.g. "आपका लैपटॉप धीरे चल रहा है?"). Do NOT write in English. Do NOT write in
Hinglish/Roman transliteration. Use everyday spoken Hindi a shop owner would
actually say out loud to a customer, not formal/literary Hindi. Common tech
terms (RAM, laptop, printer, etc.) can stay in English as commonly spoken,
mixed naturally into the Hindi sentence.

TONE: professional, friendly, helpful, simple language, easy to understand, trustworthy,
customer-focused. Never salesy or exaggerated.

STRUCTURE: Hook (first line grabs attention) -> Problem (what the viewer struggles with)
-> Solution/Product (how the shop solves it) -> Price/Offer if given, otherwise skip it
-> CTA (always end with: "{SHOP_CTA}")

HARD RULES - NEVER:
- Claim to be an "authorized service center" unless explicitly told this is true
- Promise "100% data recovery" or any absolute guarantee
- Invent warranty terms not provided
- Bash or name competitors
- Invent prices or offers not given in the input
- Claim a fake brand partnership
- Use fake testimonials or fabricated customer quotes
- Use misleading clickbait phrasing

Keep the script to 5-8 short lines, written to be read aloud naturally.
Return ONLY the script text, no preamble, no markdown.
"""


def build_user_prompt(topic: dict, angle: str) -> str:
    angle_hint = {
        "tip": "Frame this as a quick, practical tip video.",
        "explainer": "Frame this as a short explainer of what the service involves and why it matters.",
        "govt_guide": "Frame this as a helpful step-by-step guide for a government/paperwork service, emphasizing how the shop assists with the process.",
        "product_review": "Frame this as a short honest recommendation, not a hard sell.",
        "showcase": "Frame this as a showcase of the shop's work in this service area.",
    }.get(angle, "Frame this as a helpful short video.")

    return f"""Topic: {topic['title_seed']}
Category: {topic['category']}
{angle_hint}

Write the script now."""


def generate_script(topic: dict) -> str:
    """
    Calls an LLM (Groq/Gemini) to produce the script.
    Swap the endpoint/model below for whichever provider you configure in .env.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY (or adapt this function for your chosen LLM provider).")

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(topic, topic.get("angle", "tip"))},
            ],
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# --- Compliance filter: runs on every script before it moves to the next stage ---
BANNED_PHRASES = [
    "100% data recovery", "authorized service center", "official partner",
    "lifetime guarantee", "no risk", "guaranteed results",
    # Hindi equivalents
    "100% डेटा रिकवरी", "अधिकृत सेवा केंद्र", "आधिकारिक पार्टनर",
    "लाइफटाइम गारंटी", "कोई जोखिम नहीं", "गारंटीड रिजल्ट",
]


def compliance_check(script_text: str) -> tuple[bool, list[str]]:
    """Returns (passed, list_of_violations). Block the pipeline if this fails."""
    lowered = script_text.lower()
    violations = [p for p in BANNED_PHRASES if p in lowered]
    return (len(violations) == 0, violations)


if __name__ == "__main__":
    demo_topic = {"title_seed": "RAM upgrade for slow laptops", "category": "Computer & Laptop Repair", "angle": "explainer"}
    print(build_user_prompt(demo_topic, demo_topic["angle"]))
