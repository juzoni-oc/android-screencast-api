FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    RECORD_DIR=/recordings

WORKDIR /app

# Android platform tools + FFmpeg for capture and transcoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        android-sdk-platform-tools-common ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8080

CMD ["python", "-m", "src.stream_server"]
