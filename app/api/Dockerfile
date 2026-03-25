# ---------- Builder Stage ----------
FROM python:3.10-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential

WORKDIR /app

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY api/requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Runtime Stage ----------
FROM python:3.10-slim

# Create user first
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Python optimizations for containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Enable the venv in the runtime image
ENV PATH="/opt/venv/bin:$PATH"

# Create uploads directory and set permissions
RUN mkdir -p /app/uploads && chown appuser:appgroup /app/uploads

COPY --chown=appuser:appgroup --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup api /app
COPY --chown=appuser:appgroup shared /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]