import os
import re
import json
import time
import pickle
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Use absolute paths based on BASE_DIR
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'client_secrets.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.pickle')

# Default to ../edited_clips relative to this script, or use env var
DEFAULT_CLIPS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'edited_clips'))
EDITED_CLIPS_DIR = os.getenv('EDITED_CLIPS_DIR', DEFAULT_CLIPS_DIR)
HIGHLIGHTS_DIR = os.getenv('HIGHLIGHTS_DIR', os.path.abspath(os.path.join(BASE_DIR, '..', 'highlights')))

UPLOADED_CLIPS_DIR = os.path.join(EDITED_CLIPS_DIR, 'uploaded')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60')) # seconds

def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                logger.error(f"{CLIENT_SECRETS_FILE} not found. Please provide it to authenticate.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            
    return build('youtube', 'v3', credentials=creds)

def get_video_metadata(file_name):
    """
    Attempt to find metadata in highlights JSON.
    Expected clip name format: clip_01_viral.mp4
    """
    try:
        match = re.search(r"clip_(\d+)", file_name)
        if not match:
            return None, None
        
        idx = int(match.group(1)) - 1
        
        # Find the highlights file (assuming one for now as per system design)
        h_files = [f for f in os.listdir(HIGHLIGHTS_DIR) if f.endswith('_highlights.json')]
        if not h_files:
            return None, None
            
        # For now, we take the most recent highlights file or the first one
        h_file_path = os.path.join(HIGHLIGHTS_DIR, h_files[0])
        with open(h_file_path, 'r') as f:
            highlights = json.load(f)
            
        if 0 <= idx < len(highlights):
            h = highlights[idx]
            title = h.get('title', file_name)
            hashtags = h.get('hashtags', ['#shorts', '#automation'])
            return title, hashtags
    except Exception as e:
        logger.error(f"Error fetching metadata for {file_name}: {e}")
        
    return None, None

def upload_video(youtube, file_path):
    file_name = os.path.basename(file_path)
    title, hashtags = get_video_metadata(file_name)
    
    if not title:
        title = os.path.splitext(file_name)[0]
    
    # YouTube titles are max 100 chars
    final_title = title[:80] + " #shorts"
    
    description = f"{title}\n\n"
    if hashtags:
        description += " ".join(hashtags)
    description += "\n\nStay tuned for more videos!"
    
    body = {
        'snippet': {
            'title': final_title,
            'description': description,
            'tags': [t.strip('#') for t in (hashtags or [])] + ['shorts'],
            'categoryId': '22' # People & Blogs
        },
        'status': {
            'privacyStatus': os.getenv('PRIVACY_STATUS', 'public'),
            'selfDeclaredMadeForKids': False,
        }
    }
    
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
    )
    
    logger.info(f"Uploading: {file_path}")
    logger.info(f"Title: {final_title}")
    
    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            logger.info(f"Uploaded {int(status.progress() * 100)}%")
            
    logger.info(f"Upload complete! Video ID: {response['id']}")
    return response

def main():
    if not os.path.exists(UPLOADED_CLIPS_DIR):
        os.makedirs(UPLOADED_CLIPS_DIR, exist_ok=True)
        
    youtube = get_authenticated_service()
    if not youtube:
        logger.error("Failed to authenticate with YouTube. Exiting.")
        return

    logger.info("Uploader service started. Checking for one video to upload...")
    
    try:
        files = [f for f in os.listdir(EDITED_CLIPS_DIR) if f.endswith('.mp4')]
        if files:
            # Sort files to ensure we pick them in order
            files.sort()
            file_to_upload = files[0]
            file_path = os.path.join(EDITED_CLIPS_DIR, file_to_upload)
            
            try:
                upload_video(youtube, file_path)
                
                # Move to uploaded folder
                dest_path = os.path.join(UPLOADED_CLIPS_DIR, file_to_upload)
                os.rename(file_path, dest_path)
                logger.info(f"Moved {file_to_upload} to {UPLOADED_CLIPS_DIR}")
                logger.info("Upload task finished. Exiting.")
                return # Exit after one video
                
            except HttpError as e:
                logger.error(f"An HTTP error occurred: {e.resp.status} {e.content}")
            except Exception as e:
                logger.error(f"An error occurred during upload: {e}")
        
        else:
            logger.info("No new videos found in edited_clips.")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == '__main__':
    main()
