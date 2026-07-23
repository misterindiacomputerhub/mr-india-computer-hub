# Dashboard image: the Streamlit business dashboard, deployed as a normal
# always-reachable Cloud Run *service* (not a Job — this one needs to serve
# HTTP requests continuously, unlike the worker).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*
RUN find /etc -iname "policy.xml" -path "*ImageMagick*" -exec sed -i -e 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' -e 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' {} \; && (cat /etc/ImageMagick-7/policy.xml | grep -i "@\|PDF" || echo "policy check done")

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OUTPUT_DIR=/tmp/output
ENV MEDIA_LIBRARY_DIR=/app/media_library

# Cloud Run injects $PORT — Streamlit must bind to it, not a hardcoded 8501.
ENV STREAMLIT_SERVER_HEADLESS=true
CMD streamlit run dashboard.py --server.port=${PORT:-8080} --server.address=0.0.0.0
