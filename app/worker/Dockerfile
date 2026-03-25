# ---------- Builder Stage ----------
FROM python:3.10-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential

WORKDIR /app

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY worker/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Runtime Stage ----------
FROM python:3.10-slim

WORKDIR /app

# Python optimizations for containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies (ffmpeg) and clean up apt cache!
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean


RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Bring over the pre-built Python packages
COPY --chown=appuser:appgroup --from=builder /opt/venv /opt/venv

#  Set up user and permissions for the model
RUN mkdir -p /models && chown appuser:appgroup /models
ENV HF_HOME=/models

# Switch to appuser early so the model belongs to them
USER appuser

# Download the model BEFORE copying the changing source code!
# This caches perfectly. It will never re-download unless you change requirements.txt.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/models')"


COPY --chown=appuser:appgroup worker /app
COPY --chown=appuser:appgroup shared /shared

CMD ["rq", "worker", "transcriptions", "--path", "/app"]