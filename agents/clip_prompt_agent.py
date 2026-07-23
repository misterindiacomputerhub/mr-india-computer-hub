"""
clip_prompt_agent.py
Generates 3 connected, high-engagement video-generation prompts (for
Gemini/Veo) from a trending topic + the real matched shop service.
Condensed from a 5-beat UGC structure to 3 clips, each written to continue
the exact moment the previous one ended on -- not a fresh restart.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

SHOP_NAME = os.getenv("SHOP_NAME", "")
SHOP_LOCATION_SHORT = os.getenv("SHOP_LOCATION_SHORT", os.getenv("SHOP_LOCATION", ""))
SHOP_CTA = os.getenv("SHOP_CTA", "")

CLIP_SYSTEM_PROMPT = """You write 3 connected AI-video-generation prompts (for Gemini/Veo) for a
UGC-style vertical ad (9:16, 1080x1920) for {shop_name}, a local computer/mobile
repair shop in {location}.

The ad is about this real service: {service_title} (category: {category}).
The trending angle that inspired it: {topic_title}.

Produce EXACTLY 3 clips, 8-10 seconds each, forming ONE continuous story:

Clip 1 (Hook + Real Problem): open with a specific, relatable problem the
audience has actually felt (name the real symptom -- e.g. "laptop taking 5
minutes just to open Chrome", not just "slow laptop"). First 2 seconds must
stop the scroll. End on an unresolved beat so the viewer needs Clip 2.

Clip 2 (Real Demo, not a tease): pick up exactly where Clip 1 ended. Show the
technician doing the ACTUAL fix with one genuine, specific, checkable detail
a viewer could learn from (a real step, a real tool, a real cause -- e.g.
"dust-clogged fan reseated with new thermal paste", not just "he fixed it").
This clip should teach the viewer something true and useful about the
service, not just imply competence. End on a beat that sets up Clip 3.

Clip 3 (Payoff + CTA): pick up from Clip 2's ending. Show the concrete result
(measurable if possible -- "boot time back to 15 seconds"), one line of
natural social proof, then a CTA using this text if relevant: {cta}. Close on
a memorable, shareable last line.

CONTENT-DEPTH RULE (important): every clip must be about the real substance
of the service -- an actual cause, an actual step, an actual result -- not
just a mood or a brand tease. A viewer who only watches this ad should walk
away knowing one true, specific thing about {service_title}, not just that
the shop exists.

Rules:
- Each clip is a full scene: scene objective, visual description, character
  action, dialogue, emotion, camera movement, lighting, one b-roll idea, one
  sound-effect cue, background music mood, and how it transitions into the
  next clip.
- VOICE LANGUAGE IS MANDATORY AND MUST BE STATED EXPLICITLY IN EVERY CLIP:
  the character speaks in natural, spoken HINDI (Devanagari script for the
  dialogue lines, not Hinglish/Roman transliteration). Every clip's
  "visual_description" or "character_action" field must include an explicit
  line such as: "Character speaks in natural spoken Hindi with accurate
  Hindi lip-sync, casual local accent, no English voice-over." Write the
  actual "dialogue" field itself in Hindi script. A stray English
  brand/product term inside a Hindi sentence is fine; the spoken narration
  itself must not be English.
- Each clip must open by continuing the previous clip's exact moment -- it
  should not work as a standalone clip.
- No fake claims: no guaranteed results, no fake certifications, no fake
  testimonials.
- Return ONLY valid JSON, no markdown fences, no preamble.

Schema -- return a JSON array of exactly 3 objects, each with ALL of these
keys:
[
  {{
    "clip": 1,
    "duration": "8-10s",
    "scene_objective": str,
    "visual_description": str,
    "character_action": str,
    "dialogue": str,
    "emotion": str,
    "camera": str,
    "lighting": str,
    "b_roll": str,
    "sound_effects": str,
    "background_music": str,
    "transition": str,
    "prompt": str
  }},
  ... (clip 2, clip 3 same shape)
]
The "prompt" field is a single dense paragraph combining ALL the other
fields above into one paste-ready instruction for a video generation tool --
this is the only field that gets pasted into Gemini/Veo, so it must stand
alone and include the Hindi-voice instruction and full dialogue text.

VERTICAL FORMAT IS MANDATORY: every "prompt" field must explicitly state the
video is VERTICAL / PORTRAIT format, 9:16 aspect ratio, 1080x1920, shot and
framed for YouTube Shorts / Reels / TikTok -- not landscape, not widescreen.
Include a literal phrase such as: "Vertical 9:16 portrait video, 1080x1920,
shot for mobile short-form (YouTube Shorts / Reels), NOT landscape." Put this
near the start of the "prompt" paragraph so the video generation tool cannot
miss it.
"""


def generate_clip_prompts(topic_title: str, matched_service: dict) -> list:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY to use clip prompt generation.")

    system_prompt = CLIP_SYSTEM_PROMPT.format(
        shop_name=SHOP_NAME,
        location=SHOP_LOCATION_SHORT,
        service_title=matched_service["title_seed"],
        category=matched_service["category"],
        topic_title=topic_title,
        cta=SHOP_CTA,
    )

    def _parse(raw):
        raw = raw.strip("`").removeprefix("json").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[clip_prompt_agent] JSON parse failed ({e}), raw response was:\n{raw}")
            return []
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed

    def _call_groq(extra_note=""):
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the 3 connected clip prompts now." + extra_note},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        return _parse(raw), raw

    def _call_gemini(extra_note=""):
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise RuntimeError("Groq failed and GEMINI_API_KEY is not set -- no fallback available.")
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"role": "user", "parts": [{"text": system_prompt + "\n\nGenerate the 3 connected clip prompts now." + extra_note}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4000},
            },
            timeout=90,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return _parse(raw), raw

    def _call_once(extra_note=""):
        try:
            return _call_groq(extra_note)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            print(f"[clip_prompt_agent] Groq failed (status {status}), falling back to Gemini...")
            return _call_gemini(extra_note)

    clips, raw = _call_once()

    if len(clips) != 3:
        print(f"[clip_prompt_agent] WARNING: first attempt returned {len(clips)} clip(s), raw response was:\n{raw}\nRetrying once...")
        clips, raw = _call_once(
            extra_note=" IMPORTANT: your last response did not return exactly 3 clip objects in a JSON array. Return EXACTLY 3 objects in a JSON array, nothing else."
        )

    if len(clips) != 3:
        print(f"[clip_prompt_agent] Retry also failed, raw response was:\n{raw}")
        raise ValueError(f"Expected 3 clips, got {len(clips)} (see terminal for raw model output)")

    return clips


def generate_clip_prompts_checked(topic_title: str, matched_service: dict) -> list:
    """
    Same as generate_clip_prompts, but runs each clip's prompt text through
    the existing compliance filter first (fake certifications, guaranteed
    results, fake testimonials, etc.) so a bad clip never reaches the UI.
    """
    from agents import script_agent

    clips = generate_clip_prompts(topic_title, matched_service)

    for c in clips:
        passed, violations = script_agent.compliance_check(c["prompt"])
        if not passed:
            raise ValueError(f"Clip {c['clip']} prompt blocked by compliance filter: {violations}")

    return clips
