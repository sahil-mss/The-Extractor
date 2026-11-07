# Multi-stage lightweight production image with FFmpeg and modern JS runtime for yt-dlp
FROM python:3.11-slim

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install modern Deno runtime (>=2.3.0) for yt-dlp JavaScript challenge solver
COPY --from=denoland/deno:bin-2.6.0 /deno /usr/local/bin/deno

WORKDIR /app

# Copy dependency specification and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set default environment variables
ENV EXTRACTOR_CONFIG=config.yaml \
    EXTRACTOR_DOWNLOAD_DIR=/app/downloads \
    EXTRACTOR_DATA_DIR=/app/data \
    EXTRACTOR_HOST=0.0.0.0 \
    EXTRACTOR_PORT=8000 \
    HOME=/tmp \
    DENO_DIR=/tmp/.deno \
    PIP_CACHE_DIR=/tmp/.pip-cache

# Create non-root user and setup directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/downloads /app/data && \
    chown -R appuser:appuser /app

USER appuser

# Healthcheck hitting /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/healthz || exit 1

# Create volume mount points for downloads and database persistence
VOLUME ["/app/downloads", "/app/data"]

EXPOSE 8000

CMD ["python", "main.py", "--no-browser"]
