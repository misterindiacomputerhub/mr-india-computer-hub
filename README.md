# Shop Auto-Upload Pipeline

Automates 2-3 YouTube videos/day for a local shop (computer repair, printer,
CCTV, cyber café/govt services, networking, accessories, photography), using
the shop's own service list as the content source instead of trending-topic
discovery.

## Pipeline stages

```
Content Queue (data/services.json)
   -> Script Agent (brand-voice + compliance rules hardcoded)
   -> Title A/B Agent
   -> TTS Agent (voiceover)
   -> Video Agent (real shop photos/clips + captions, via ffmpeg/moviepy)
   -> Upload Agent (YouTube Data API)
   -> Performance logging -> feeds back into queue prioritization
```

## Setup

1. `pip install -r requirements.txt` (also install `ffmpeg` on the system)
2. Copy `.env.example` to `.env` and fill in:
   - `GROQ_API_KEY` (or swap the LLM call in `agents/script_agent.py`)
   - Shop name, location, contact, CTA
3. Add real photos/video clips per topic:
   `media_library/<topic_id>/photo1.jpg`, matching the `id` fields in
   `data/services.json` (e.g. `media_library/ram_upgrade/`).
4. Set up YouTube OAuth (see docstring in `agents/upload_agent.py`) and place
   `client_secret.json` in the project root.

## Build order (don't wire the scheduler on day 1)

1. Run `python main.py` once — verifies the whole chain end-to-end for one topic.
   Check the script quality, voice, and rendered video by hand before trusting it.
2. Once a handful of manual runs look right, start `python scheduler.py` to run
   automatically at the times in `UPLOAD_TIMES`.
3. Deploy: push this repo to Railway/Render as a worker (`Procfile` included),
   set the `.env` vars in the dashboard, and mount a persistent volume for
   `pipeline.db` so history survives restarts.
4. Let it run for a couple weeks, then check `database.best_performing_categories()`
   to see which service categories are earning more views — that's the signal
   to make more of.

## Compliance note

`agents/script_agent.py` hardcodes a list of claims the script generator must
never make (fake authorized-service-center claims, guaranteed data recovery,
invented prices, fake testimonials, etc.) plus a `compliance_check()` filter
that blocks a video from proceeding if a banned phrase slips through. Review
and extend `BANNED_PHRASES` before going live — this list is a starting point,
not a complete legal safeguard.
