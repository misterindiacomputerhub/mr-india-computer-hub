"""
tts_agent.py
Converts a script into a Hindi voiceover using Sarvam AI's Bulbul v3 TTS
model. Defaults to the "pooja" voice. Chunks long scripts to stay safely
under Sarvam's per-request character limit, then stitches the audio back
together.

Requires: SARVAM_API_KEY environment variable, requests package.
    pip install requests --break-system-packages
"""
import os
import re
import base64
import requests

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

VOICE = os.getenv("TTS_VOICE", "pooja")
LANGUAGE = os.getenv("TTS_LANGUAGE", "hi-IN")
MODEL = os.getenv("TTS_MODEL", "bulbul:v3")
MAX_CHUNK_CHARS = 450  # stay safely under Sarvam's per-request limit


def _get_api_key() -> str:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "SARVAM_API_KEY environment variable not set. "
            "export SARVAM_API_KEY='your_key_here'"
        )
    return api_key


def _split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Splits text on sentence boundaries, keeping each chunk under max_chars."""
    sentences = re.split(r'(?<=[।.!?])\s+', text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def _synthesize_chunk(text: str, voice: str) -> bytes:
    api_key = _get_api_key()
    resp = requests.post(
        SARVAM_TTS_URL,
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "target_language_code": LANGUAGE,
            "speaker": voice,
            "model": MODEL,
            "pace": 1.0,
            "output_audio_codec": "mp3",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Sarvam TTS failed ({resp.status_code}): {resp.text}")

    audio_b64 = resp.json()["audios"][0]
    return base64.b64decode(audio_b64)


def generate_voiceover(script_text: str, out_path: str, voice: str = VOICE) -> str:
    chunks = _split_into_chunks(script_text)
    audio_bytes_list = [_synthesize_chunk(chunk, voice) for chunk in chunks]

    # mp3 chunks can be concatenated directly at the byte level
    with open(out_path, "wb") as f:
        for audio_bytes in audio_bytes_list:
            f.write(audio_bytes)

    return out_path


if __name__ == "__main__":
    demo_script = (
        "नमस्ते! आपका कंप्यूटर धीरे चल रहा है? "
        "रैम अपग्रेड से यह समस्या ठीक हो सकती है।"
    )
    generate_voiceover(demo_script, "./output/demo_voiceover.mp3")
    print("Saved ./output/demo_voiceover.mp3")
