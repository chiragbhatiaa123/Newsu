from PIL import Image, ImageDraw
import requests
import io
import logging

logger = logging.getLogger(__name__)

def create_gradient_overlay(width, height, config):
    """
    Creates a vertical gradient overlay based on config.
    """
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Check overrides in canvas OR gradient config
    grad_height_ratio = config.get('canvas', {}).get('gradient_height') or config.get('gradient', {}).get('height_ratio', 0.85)

    max_alpha = config.get('gradient', {}).get('max_alpha', 255)
    start_color = tuple(config.get('gradient', {}).get('start_color', [0,0,0]))
    r, g, b = start_color
    
    gradient_height = int(height * grad_height_ratio) 
    start_y = height - gradient_height
    
    # Optimization: Draw reduced steps instead of per-line if performance needed, but per-line is fine for single image.
    for y in range(start_y, height):
        ratio = (y - start_y) / gradient_height
        alpha = int(ratio * max_alpha)
        draw.line([(0, y), (width, y)], fill=(r, g, b, alpha))
        
    return overlay

def prepare_background(image_url, width, height, bg_color):
    """
    Fetches, resizes, and crops the background image.
    Returns: processed_image (Image)
    """
    bg_img = Image.new('RGB', (width, height), color=tuple(bg_color))
    
    if not image_url:
        return bg_img
        
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(image_url, headers=headers, timeout=5)
        if response.status_code == 200:
            downloaded_img = Image.open(io.BytesIO(response.content)).convert('RGB')
            
            # Target Resize (Cover)
            img_ratio = downloaded_img.width / downloaded_img.height
            target_ratio = width / height
            
            if img_ratio > target_ratio:
                # Too wide
                scale_height = height
                scale_width = int(scale_height * img_ratio)
                downloaded_img = downloaded_img.resize((scale_width, scale_height), Image.Resampling.LANCZOS)
                left = (scale_width - width) // 2
                downloaded_img = downloaded_img.crop((left, 0, left + width, height))
            else:
                # Too tall
                scale_width = width
                scale_height = int(scale_width / img_ratio)
                downloaded_img = downloaded_img.resize((scale_width, scale_height), Image.Resampling.LANCZOS)
                top = (scale_height - height) // 2
                downloaded_img = downloaded_img.crop((0, top, width, top + height))
                
            return downloaded_img
            
    except Exception as e:
        logger.error(f"Failed to process background image: {e}")
        
    return bg_img
