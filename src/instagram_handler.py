import logging
import os
import re
import uuid
import yt_dlp

logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.getcwd(), 'temp_instagram')
os.makedirs(TEMP_DIR, exist_ok=True)

class InstagramHandler:
    @staticmethod
    def is_instagram_url(url):
        return 'instagram.com' in url.lower()

    @staticmethod
    def get_content_type(url):
        if '/reel/' in url or '/reels/' in url:
            return 'REEL'
        if '/p/' in url:
            return 'POST'
        return 'UNKNOWN'

    @staticmethod
    def process_url(url):
        """
        Downloads media and extracts metadata.
        Returns dict: {
            'type': 'video' | 'image',
            'path': str,  # Path to local file
            'caption': str,
            'author': str,
            'date': str
        }
        """
        ctype = InstagramHandler.get_content_type(url)
        logger.info(f"Processing Instagram {ctype}: {url}")

        try:
            ctype = InstagramHandler.get_content_type(url)
            
            # Common options
            ydl_opts = {
                'outtmpl': os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.%(ext)s"),
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 50 * 1024 * 1024,
                'ignoreerrors': True, # Critical for image-only posts
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 1. Image Post Handling
                if ctype == 'POST':
                    logger.info("Handling as Image Post - Metadata extraction only")
                    # Don't try to download video, just get info
                    info = ydl.extract_info(url, download=False)
                    
                    if not info:
                        logger.error("No info returned from yt-dlp")
                        return None

                    # Metadata
                    caption = info.get('description') or info.get('title') or ""
                    author = info.get('uploader') or "Instagram"
                    upload_date = info.get('upload_date')
                    
                    # Format Date
                    date_str = "Latest"
                    if upload_date and len(upload_date) == 8:
                        from datetime import datetime
                        dt = datetime.strptime(upload_date, "%Y%m%d")
                        date_str = dt.strftime("%d %b, %Y")

                    return {
                        'type': 'post_text', # distinct type to trigger text flow
                        'path': None,
                        'caption': caption,
                        'author': author,
                        'date': date_str,
                        'raw_info': info
                    }

                # 2. Reel/Video Handling
                else: 
                    # Default: Download Video
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                    # Metadata
                    caption = info.get('description') or info.get('title') or ""
                    author = info.get('uploader') or "Instagram"
                    upload_date = info.get('upload_date')
                    
                    date_str = "Latest"
                    if upload_date and len(upload_date) == 8:
                        from datetime import datetime
                        dt = datetime.strptime(upload_date, "%Y%m%d")
                        date_str = dt.strftime("%d %b, %Y")

                    # Fallback to check if it downloaded an image (sometimes yt-dlp does that)
                    media_type = 'video'
                    if filename.endswith('.jpg') or filename.endswith('.png') or filename.endswith('.webp'):
                        media_type = 'image'

                    return {
                        'type': media_type,
                        'path': filename,
                        'caption': caption,
                        'author': author,
                        'date': date_str, 
                        'raw_info': info
                    }

        except Exception as e:
            logger.error(f"Instagram processing failed: {e}")
            return None
