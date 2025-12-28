import logging
import os
import yt_dlp
import uuid

logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.getcwd(), 'temp_videos')
os.makedirs(TEMP_DIR, exist_ok=True)

def download_video(url):
    """
    Downloads video from URL (Instagram, YouTube, etc.) using yt-dlp.
    Returns path to the downloaded MP4 file.
    """
    try:
        # Unique filename
        filename = f"{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(TEMP_DIR, filename)
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'max_filesize': 50 * 1024 * 1024, # 50MB limit
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Find the actual filename
            filename = ydl.prepare_filename(info)
            # ydl might change extension (e.g. .mkv if best), so we return actual
            return filename
            
    except Exception as e:
        logger.error(f"Video download failed: {e}")
        return None
