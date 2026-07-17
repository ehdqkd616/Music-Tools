# Base worker image — used for the download and dsp queues (and celery beat).
# Separation gets its own image (Dockerfile.separate) since it needs torch/demucs.
FROM python:3.11-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg rubberband-cli libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY services/workers/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/common ./common
COPY services/workers ./workers

ENV PYTHONPATH=/srv PYTHONUNBUFFERED=1

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=INFO"]
