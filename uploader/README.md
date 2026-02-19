# YouTube Shorts Uploader

This service automatically uploads `.mp4` files from the `edited_clips` folder to YouTube as Shorts.

## Setup

### 1. Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **YouTube Data API v3**.
4. Go to **Credentials** and create an **OAuth 2.0 Client ID** (Desktop Application).
5. Download the JSON file and rename it to `client_secrets.json`.
6. Place `client_secrets.json` in this `uploader` folder.

### 2. Authentication (First Time)
Since this runs in Docker, it cannot easily open a browser for the OAuth flow.
1. Install the requirements locally: `pip install -r requirements.txt`
2. Run the script once locally: `python3 uploader.py`
3. Follow the instructions in your browser to authorize the app.
4. This will create a `token.pickle` file in this folder.
5. Once you have `token.pickle`, the Docker container can use it to authenticate without a browser.

### 3. Running with Docker
The uploader expects the `edited_clips` folder to be mounted. 

In your `docker-compose.yml`, add:

```yaml
  uploader:
    build: ./uploader
    volumes:
      - ./edited_clips:/app/edited_clips
      - ./uploader/token.pickle:/app/token.pickle
      - ./uploader/client_secrets.json:/app/client_secrets.json
    environment:
      - CHECK_INTERVAL=300
      - PRIVACY_STATUS=public
```

## How it works
- It monitors `/app/edited_clips` for `.mp4` files.
- It uploads one video at a time.
- After a successful upload, the video is moved to `/app/edited_clips/uploaded/`.
- It appends `#shorts` to the filename to ensure it's treated as a Short.
