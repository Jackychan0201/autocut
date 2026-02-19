FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Environment variables
ENV EDITED_CLIPS_DIR=/app/edited_clips
ENV CHECK_INTERVAL=60
ENV PRIVACY_STATUS=public

# We expect edited_clips to be mounted here
VOLUME ["/app/edited_clips"]

CMD ["python", "uploader.py"]
