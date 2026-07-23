#!/usr/bin/env bash
# Deployment commands for moving Mr India Computer Hub off Render onto
# Firebase's Blaze-plan billing account, using Cloud Run underneath.
# Run these one block at a time (not as one blind script) — several need
# your project ID, region, and secret values filled in first.
set -euo pipefail

PROJECT_ID="mich-123"
REGION="asia-south1"                    # Mumbai — closest to Bihar; change if you prefer

gcloud config set project "$PROJECT_ID"

# ---------------------------------------------------------------------------
# 0. One-time setup
# ---------------------------------------------------------------------------
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

# ---------------------------------------------------------------------------
# 1. Store secrets in Secret Manager (never in the image / not in git)
#    Repeat --data-file for each secret. YT_TOKEN_FILE/client_secret.json
#    are mounted as files (see --set-secrets with a /path target below);
#    everything else is a plain env var secret.
# ---------------------------------------------------------------------------
gcloud secrets create GROQ_API_KEY   --data-file=<(printf '%s' "PASTE_VALUE")
gcloud secrets create DATABASE_URL   --data-file=<(printf '%s' "PASTE_NEON_POSTGRES_URL")
gcloud secrets create YT_CLIENT_SECRET_JSON --data-file="./client_secret.json"
gcloud secrets create YT_TOKEN_JSON         --data-file="./token.json"
# repeat for ELEVENLABS_API_KEY / GEMINI_API_KEY / YOUTUBE_API_KEY if you use them

# ---------------------------------------------------------------------------
# 2. Build + push both images (Artifact Registry, via Cloud Build — no local
#    Docker needed)
# ---------------------------------------------------------------------------
gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT_ID/mr-india/worker" \
  -f Dockerfile.worker .

gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT_ID/mr-india/dashboard" \
  -f Dockerfile.dashboard .

# ---------------------------------------------------------------------------
# 3. Worker: Cloud Run JOB (not a service) — this is the piece that replaces
#    your Render worker + its 512MB cap. Bump memory/cpu freely; Cloud Run
#    on Blaze goes up to 32Gi RAM / 8 vCPU per instance, and you only pay for
#    the ~minute or two each run actually takes, not 24/7 like Render.
# ---------------------------------------------------------------------------
gcloud run jobs create mr-india-worker \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/mr-india/worker" \
  --region "$REGION" \
  --memory 2Gi \
  --cpu 2 \
  --max-retries 1 \
  --task-timeout 900 \
  --set-env-vars "SHOP_NAME=Mr India Computer Hub,SHOP_LOCATION=Biraul,VIDEOS_PER_DAY=3" \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,GROQ_API_KEY=GROQ_API_KEY:latest,YT_CLIENT_SECRETS_FILE=YT_CLIENT_SECRET_JSON:latest,YT_TOKEN_FILE=YT_TOKEN_JSON:latest"

# Cloud Scheduler calls this job once an hour — replacing scheduler.py's
# own time.sleep(3600) loop.
gcloud scheduler jobs create http mr-india-worker-hourly \
  --location "$REGION" \
  --schedule "0 * * * *" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/mr-india-worker:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud iam service-accounts list --filter='displayName:Compute Engine default' --format='value(email)')"

# ---------------------------------------------------------------------------
# 4. Dashboard: Cloud Run SERVICE (needs to be reachable any time you check it)
# ---------------------------------------------------------------------------
gcloud run deploy mr-india-dashboard \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/mr-india/dashboard" \
  --region "$REGION" \
  --memory 1Gi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest"
  # drop --allow-unauthenticated if this dashboard shows customer data —
  # see the note in MIGRATION.md

# ---------------------------------------------------------------------------
# 5. Optional: point Firebase Hosting at the dashboard so it sits behind your
#    Firebase project's own domain (Hosting proxies to Cloud Run for free on
#    Blaze). Run this from the project root after `firebase init hosting`.
# ---------------------------------------------------------------------------
# firebase deploy --only hosting
