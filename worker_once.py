"""
worker_once.py
Cloud Run Job entrypoint. Runs exactly one pass of what scheduler.py's
run_forever() loop does per hour — poll performance stats, then generate
a video if the current hour is a "best hour" and today's quota isn't met —
then exits.

This replaces scheduler.py's `while True: ... time.sleep(3600)` loop, which
was designed for a single always-on process (fine on Render/a VM, wasteful
and fragile on serverless). Cloud Scheduler now provides the hourly cadence
by invoking this Job once per hour; each run gets a fresh container with
the full memory/CPU you configure, so there's no long-lived process to leak
memory or hit Render's 512MB ceiling.

Deploy + schedule this with the commands in deploy.sh.
"""
import os
import traceback

from dotenv import load_dotenv
load_dotenv()

import database as db
from main import OUTPUT_DIR
from scheduler import poll_performance, maybe_generate_video


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    db.init_db()
    print("[worker_once] starting single pass")
    try:
        poll_performance()
        maybe_generate_video()
    except Exception:
        traceback.print_exc()
        raise  # non-zero exit so Cloud Scheduler/Cloud Run marks the run failed
    print("[worker_once] pass complete")


if __name__ == "__main__":
    main()
