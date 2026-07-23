# Migrating Mr India Computer Hub off Render → Firebase (Blaze) + Cloud Run

## What's in this folder
- `Dockerfile.worker` — builds the pipeline (scheduler + video rendering) as a Cloud Run **Job**
- `worker_once.py` — new entrypoint: runs one scheduler pass and exits (fits a Job triggered hourly, instead of a process that sleeps forever)
- `Dockerfile.dashboard` — builds the Streamlit dashboard as a Cloud Run **service**
- `.dockerignore` — keeps secrets and local junk out of the built image
- `deploy.sh` — the actual `gcloud`/`firebase` commands, annotated, run manually block by block
- `firebase.json` — points Firebase Hosting at the dashboard Cloud Run service (optional, cosmetic — gives you a firebaseapp.com URL instead of a raw Cloud Run URL)

## Why Cloud Run Jobs instead of "Firebase" directly
Firebase's own compute (Cloud Functions) is built for short request/response calls, not a process that loops forever rendering video with ffmpeg. Cloud Run — which your Firebase Blaze billing account also covers — is built for exactly this: you control the Dockerfile, and you can set memory anywhere up to 32GiB (vs. Render's 512MB cap you're currently hitting).

I also split your one worker process into two pieces:
- **Cloud Run Job**, triggered hourly by Cloud Scheduler, running `worker_once.py` (poll stats → maybe generate one video → exit). This replaces `scheduler.py`'s internal `time.sleep(3600)` loop. Each hourly run gets a fresh container with the full 2GB+ you give it, so there's nothing that can slowly leak memory over days like a long-lived process can.
- **Cloud Run service** for `dashboard.py`, since that one genuinely needs to be reachable any time you open it.

This also changes your bill from "pay for a worker running 24/7" to "pay for ~1–2 minutes of compute per hour" — likely cheaper than Render too.

## Good news on the database
`database.py` is already on **Postgres via Neon**, not local SQLite — so there's no database migration needed here, and no risk of losing data when a Cloud Run container restarts (which is a real risk with SQLite in stateless containers). Just carry `DATABASE_URL` over into the new environment as a secret.

## Things I flagged while reading the repo (worth knowing about)
1. **Secrets were in the zip you uploaded**: `.env`, `client_secret.json`, and `token.json` all contain live credentials. I excluded them from `mr-india-computer-hub-clean.zip` and from the Docker build context (`.dockerignore`). Load them into Secret Manager instead (commands in `deploy.sh`) — never bake them into an image, since images get cached/shared more widely than a `.env` file on disk.
2. **`requirements.txt` has duplicate entries** (`streamlit`, `pandas`, `psycopg2-binary`, `moviepy`, `requests` each listed twice). Harmless for `pip install`, but worth cleaning up.
3. **`scheduler.log` shows a live bug**: YouTube stats polling is failing with `403 Insufficient Permission` — the OAuth token in `token.json` doesn't have the `youtube.readonly`/analytics scope needed for `fetch_video_stats`. Re-run your OAuth consent flow with the right scopes before/after migrating, or performance tracking (and therefore the "adaptive best hour" logic) will keep silently failing.
4. **Dashboard has customer PII**: `database.py`'s `customer_services` table stores customer names and mobile numbers. The `deploy.sh` command deploys it with `--allow-unauthenticated` for simplicity — if this dashboard shouldn't be publicly reachable by anyone with the URL, drop that flag and set up Identity-Aware Proxy or Firebase Auth in front of it instead.
5. **`output/` and `generated_media/` were ~80MB of already-rendered videos/audio** — I left these out of both the clean zip and the Docker image since they're regenerated per run and would just bloat every build.

## Order of operations
1. Push secrets to Secret Manager (`deploy.sh` step 1)
2. Build + push both images (step 2)
3. Create the Cloud Run Job + Cloud Scheduler trigger for the worker (step 3)
4. Deploy the dashboard service (step 4)
5. Test: `gcloud run jobs execute mr-india-worker --region asia-south1` to trigger one run manually and watch the logs before trusting the hourly schedule
6. Once you're confident it's stable, decommission the Render worker
