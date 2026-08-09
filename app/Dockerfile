# Standalone Sixty Days submission image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY spine/ ./spine/
COPY service/ ./service/
COPY sixty_days/ ./sixty_days/
COPY web/ ./web/

# The scanned reports and the output Gemini actually produced for them. Shipped so the live demo
# ingests real recorded model output rather than anything hand-written, and so a judge can fetch
# both the image and its extraction from the deployed service.
COPY fixtures/ ./fixtures/

# Cloud Run supplies PORT. Never hardcode 8080.
ENV PORT=8080
EXPOSE 8080

# Non-root. A container that does not need root should not have it.
RUN useradd --create-home --uid 10001 runner
USER runner

CMD ["sh", "-c", "exec uvicorn service.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
