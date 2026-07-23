"""
generate_voice_samples.py
Generates 10 demo Hindi TTS samples using Sarvam AI's Bulbul v3 model
so you can pick your channel's voice. Saves each as a .wav file in
voice_samples/.

Requires: SARVAM_API_KEY environment variable, requests package.
"""
import os
import base64
import requests

API_KEY = os.environ.get("SARVAM_API_KEY")
if not API_KEY:
    raise EnvironmentError("Set SARVAM_API_KEY first: export SARVAM_API_KEY='your_key'")

URL = "https://api.sarvam.ai/text-to-speech"

# 5 male + 5 female voices from Bulbul v3's speaker catalog
VOICES = [
    ("shubh", "male"), ("aditya", "male"), ("rahul", "male"),
    ("rohan", "male"), ("dev", "male"),
    ("ritu", "female"), ("priya", "female"), ("neha", "female"),
    ("pooja", "female"), ("simran", "female"),
]

DEMO_TEXT = (
    "नमस्ते! आपका कंप्यूटर ठीक करने के लिए हम यहाँ हैं। "
    "चाहे स्क्रीन टूटी हो, डेटा रिकवरी करनी हो, या नया प्रिंटर सेट करना हो — "
    "हम हर समस्या का समाधान देते हैं।"
)

os.makedirs("voice_samples", exist_ok=True)

for speaker, gender in VOICES:
    resp = requests.post(
        URL,
        headers={
            "api-subscription-key": API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "text": DEMO_TEXT,
            "target_language_code": "hi-IN",
            "speaker": speaker,
            "model": "bulbul:v3",
            "pace": 1.0,
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"[{speaker}] FAILED: {resp.status_code} {resp.text}")
        continue

    data = resp.json()
    audio_b64 = data["audios"][0]
    audio_bytes = base64.b64decode(audio_b64)

    out_path = f"voice_samples/{speaker}_{gender}.wav"
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    print(f"[{speaker}] saved -> {out_path}")

print("\nDone. Play the files in voice_samples/ and tell me which one you like.")
