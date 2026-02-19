FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and ffmpeg for yt-dlp
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade yt-dlp


# Copy app
COPY . .

# Make downloads folder available
VOLUME ["/downloads"]

CMD ["python", "Downloader.py"]
