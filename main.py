import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

"""
main.py
The pipeline orchestrator. Runs ONE topic all the way from queue -> uploaded.
scheduler.py calls this N times per day (VIDEOS_PER_DAY).

Run manually first to verify quality before wiring in the scheduler:
    python main.py
"""
import os
import uuid
import json
import traceback
from dotenv import load_dotenv

import database as db
from agents import script_agent, title_agent, tts_agent, video_agent, upload_agent

load_dotenv()

SHOP_NAME = os.getenv("SHOP_NAME", "Your Shop Name")
SHOP_LOCATION = os.getenv("SHOP_LOCATION", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")


def run_one_topic(topic: dict) -> str | None:
    """
    Runs the full stage chain for a single content-queue topic.
    Each stage updates the DB so a failure at any point is visible and
    retryable without redoing the earlier, already-successful stages.
    """
    video_id = str(uuid.uuid4())
    db.insert_video(video_id, topic["id"], title=topic["title_seed"])

    try:
        # 1. Script
        script_text = script_agent.generate_script(topic)
        passed, violations = script_agent.compliance_check(script_text)
        if not passed:
            db.update_video(video_id, status="failed")
            print(f"[{video_id}] Blocked by compliance filter: {violations}")
            return None
        db.update_video(video_id, script=script_text, status="scripted")

        # 2. Title A/B
        variants = title_agent.generate_title_variants(topic["title_seed"], SHOP_NAME, SHOP_LOCATION)
        best = title_agent.pick_best_variant(variants)
        db.update_video(video_id, title=best["title"], title_variant_label=best["label"])

        # 3. Voiceover
        voice_path = os.path.join(OUTPUT_DIR, f"{video_id}_voice.mp3")
        tts_agent.generate_voiceover(script_text, voice_path)
        db.update_video(video_id, status="voiced")

        # 4. Video render
        video_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
        video_agent.render_video(script_text, voice_path, topic["id"], topic["title_seed"], video_path)
        db.update_video(video_id, status="rendered")

        # 5. Upload
        contact_lines = []
        if os.getenv("SHOP_PHONE"):
            contact_lines.append(f"📞 Call: {os.getenv('SHOP_PHONE')}")
        if os.getenv("SHOP_MAPS_LINK"):
            contact_lines.append(f"📍 Location: {os.getenv('SHOP_MAPS_LINK')}")
        if os.getenv("SHOP_INSTAGRAM"):
            contact_lines.append(f"📸 Instagram: {os.getenv('SHOP_INSTAGRAM')}")
        if os.getenv("SHOP_FACEBOOK"):
            contact_lines.append(f"📘 Facebook: {os.getenv('SHOP_FACEBOOK')}")
        contact_block = "\n".join(contact_lines)

        description = (
            f"{script_text}\n\n"
            f"{os.getenv('SHOP_CTA', '')}\n\n"
            f"{contact_block}"
        ).strip()
        youtube_id = upload_agent.upload_video(
            video_path, best["title"], description, tags=[topic["category"], SHOP_NAME]
        )
        db.update_video(video_id, status="uploaded", youtube_video_id=youtube_id,
                         uploaded_at=__import__("datetime").datetime.now(
                             __import__("datetime").timezone.utc).isoformat())

        # 6. Mark queue rotation
        db.mark_topic_used(topic["id"])

        print(f"[{video_id}] Uploaded -> https://youtube.com/watch?v={youtube_id}")
        return youtube_id

    except Exception as e:
        db.update_video(video_id, status="failed")
        print(f"[{video_id}] FAILED at some stage: {e}")
        traceback.print_exc()
        return None


def run_daily_batch(n: int | None = None):
    n = n or int(os.getenv("VIDEOS_PER_DAY", 3))
    topics = db.next_topics(n)
    if not topics:
        print("Content queue is empty — add more topics to data/services.json and re-seed.")
        return
    for topic in topics:
        run_one_topic(topic)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    db.init_db()
    with open("data/services.json") as f:
        db.seed_queue_from_json(json.load(f))
    run_daily_batch()
