import logging
import os
import subprocess
import uuid

logger = logging.getLogger(__name__)

def process_video_with_overlay(video_path, overlay_image_bytes):
    """
    1. Crops video to 9:16 (1080x1920).
    2. Overlays the transparent PNG.
    3. Outputs MP4.
    """
    try:
        # save overlay bytes to temp file
        overlay_path = video_path.replace(".mp4", "_overlay.png")
        with open(overlay_path, "wb") as f:
            f.write(overlay_image_bytes.getbuffer())
            
        output_path = video_path.replace(".mp4", "_final.mp4")
        
        # FFmpeg Command
        # 1. Input Video
        # 2. Input Overlay
        # 3. Filter Complex:
        #    - [0:v] scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1 [bg];
        #    - [bg][1:v] overlay=0:0 [out]
        # 4. Map [out] and 0:a (audio)
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', overlay_path,
            '-filter_complex', 
            '[0:v]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350,setsar=1[bg];[bg][1:v]overlay=0:0',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k', # Ensure audio is re-encoded/copied
            '-movflags', '+faststart',
            output_path
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr.decode()}")
            return None
            
        # Cleanup temp overlay
        try: os.remove(overlay_path)
        except: pass
        
        return output_path
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return None
