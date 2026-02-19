# Stage 1: Get FFmpeg binary
FROM mwader/static-ffmpeg:7.0 AS ffmpeg

# Stage 2: Final image
FROM python:3.11-slim

# Install minimal libraries for font support (required for captions)
RUN apt-get update && \
    apt-get install -y libfontconfig1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy FFmpeg from stage 1
COPY --from=ffmpeg /ffmpeg /usr/local/bin/
COPY --from=ffmpeg /ffprobe /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy code and requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Ensure fonts are available (essential for ASS rendering)
RUN mkdir -p /app/fonts
# Note: font is copied as part of 'COPY . .' but we can be explicit if preferred.
# The .dockerignore will handle excluding the large video folders.