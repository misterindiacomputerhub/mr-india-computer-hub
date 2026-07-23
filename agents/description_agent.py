"""
description_agent.py

Assembles the final YouTube description in the shop's fixed format:
  hook -> feature bullets -> audience line -> location block -> disclaimer -> hashtags

Shop info is read from the same .env vars the rest of the pipeline uses,
so it always stays in sync with SHOP_NAME / SHOP_LOCATION / SHOP_MAPS_LINK.
"""
import os
from dotenv import load_dotenv
load_dotenv()

SHOP_NAME = os.getenv("SHOP_NAME", "MISTER INDIA COMPUTER HUB")
SHOP_LOCATION = os.getenv("SHOP_LOCATION", "Jagannathpur, Biraul, Darbhanga, Bihar, India")
SHOP_MAPS_LINK = os.getenv("SHOP_MAPS_LINK", "https://maps.app.goo.gl/RgPhMFHBdk2nePyw8")
DISCLAIMER = "Offer valid for a limited time. Terms & conditions may apply."
BASE_HASHTAGS = ["Shorts", "ComputerRepair", "Students", "TechTips", "MisterIndiaComputerHub"]


def _format_bullets(features):
    return "\n".join(f"- {item}" for item in features)


def _format_hashtags(topic_tags):
    seen, ordered = set(), []
    for tag in list(topic_tags) + BASE_HASHTAGS:
        clean = tag.strip().lstrip("#").replace(" ", "")
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            ordered.append(clean)
    return " ".join(f"#{t}" for t in ordered)


def generate_description(hook: str, features: list, audience_line: str, tags: list) -> str:
    sections = []
    if hook:
        sections.append(hook.strip())
    if features:
        sections.append(_format_bullets(features))
    if audience_line:
        sections.append(audience_line.strip())
    sections.append(f"📍 {SHOP_NAME}\n{SHOP_LOCATION}\n({SHOP_MAPS_LINK})")
    sections.append(f"⚠️ {DISCLAIMER}")
    sections.append(_format_hashtags(tags))
    return "\n\n".join(sections)
