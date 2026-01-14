# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg (required for yt-dlp to merge formats)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose port (Render uses PORT env var)
EXPOSE 8000

# Run with gunicorn
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"]
