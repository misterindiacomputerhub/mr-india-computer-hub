"""
scheduler.py
Long-running adaptive scheduler for MR India Computer Hub.

Every hour, on the hour, it:
  1. Polls YouTube view/like/comment stats for recently-uploaded videos and
     logs them (feeds the velocity analysis over time).
  2. Recomputes which hour-of-day tends to produce the fastest early view
     growth, based on accumulated performance history.
  3. If the current local hour is one of the top N "best hours" (N =
     VIDEOS_PER_DAY) AND today's video quota isn't met yet, generates and
     uploads one video from the content queue.

Cold start: until enough performance history exists, falls back to fixed
default hours (9am / 2pm / 7pm local) so the channel keeps posting on a
sane schedule while it "learns."

Run with (leave it running — it loops forever):
    python scheduler.py
Recommended: run inside `tmux`/`screen`, or with `nohup python scheduler.py &`,
so it survives you closing the terminal.
"""
import os
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import database as db
from agents import upload_agent
from main import run_one_topic, OUTPUT_DIR

VIDEOS_PER_DAY = int(os.getenv("VIDEOS_PER_DAY", 3))
DEFAULT_HOURS = [int(h) for h in os.getenv("DEFAULT_POST_HOURS", "9,14,19").split(",")]
CHECK_INTERVAL_SECONDS = 3600  # hourly
TRACKING_WINDOW_HOURS = 72  # stop polling a video's stats after 3 days


def poll_performance():
    tracked = db.get_tracked_videos(max_age_hours=TRACKING_WINDOW_HOURS)
    for v in tracked:
        try:
            stats = upload_agent.fetch_video_stats(v["youtube_video_id"])
            db.log_performance(v["video_id"], stats["views"], stats["likes"], stats["comments"])
            print(f"[scheduler] logged stats for {v['video_id']}: {stats}")
        except Exception as e:
            print(f"[scheduler] failed to fetch stats for {v['video_id']}: {e}")


def get_best_hours(top_n):
    velocities = db.velocity_by_upload_hour()
    if not velocities:
        print(f"[scheduler] not enough performance data yet — using default hours {DEFAULT_HOURS[:top_n]}")
        return DEFAULT_HOURS[:top_n]
    ranked = sorted(velocities.items(), key=lambda kv: kv[1], reverse=True)
    best = [h for h, _ in ranked[:top_n]]
    print(f"[scheduler] adaptive best hours: {best} (from {len(velocities)} hour-buckets of history)")
    return best


def maybe_generate_video():
    today_count = db.videos_created_today()
    if today_count >= VIDEOS_PER_DAY:
        print(f"[scheduler] daily quota reached ({today_count}/{VIDEOS_PER_DAY}) — skipping this hour")
        return

    current_hour = datetime.now().hour  # server-local hour, matches velocity_by_upload_hour's basis
    best_hours = get_best_hours(VIDEOS_PER_DAY)

    if current_hour not in best_hours:
        print(f"[scheduler] hour {current_hour} not in best hours {best_hours} — skipping")
        return

    topics = db.next_topics(1)
    if not topics:
        print("[scheduler] content queue is empty — add more topics to data/services.json")
        return

    print(f"[scheduler] hour {current_hour} is a best hour and quota not met — generating a video...")
    try:
        run_one_topic(topics[0])
    except Exception:
        traceback.print_exc()


def run_forever():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    db.init_db()
    print(f"[scheduler] started. Checking hourly. Target: {VIDEOS_PER_DAY} videos/day at adaptive best hours.")
    while True:
        try:
            poll_performance()
            maybe_generate_video()
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
