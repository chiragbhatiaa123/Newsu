from PIL import Image
import logging
import os

logger = logging.getLogger(__name__)

def draw_logo(image, config):
    """
    Draws the logo on the image based on config.
    Returns the modified image.
    """
    try:
        logo_conf = config.get('logo', {})
        path = logo_conf.get('path', '')
        
        # Basic validation
        if not path or not os.path.exists(path):
            if path:
                logger.warning(f"Logo path not found: {path}")
            return image

        # Load Logo
        try:
            logo = Image.open(path).convert("RGBA")
        except Exception as e:
            logger.error(f"Could not open logo file: {e}")
            return image
        
        # Resize
        target_w = logo_conf.get('target_width', 150)
        # Avoid division by zero
        if logo.width == 0:
            return image
            
        w_percent = (target_w / float(logo.width))
        h_size = int((float(logo.height) * float(w_percent)))
        
        logo = logo.resize((target_w, h_size), Image.Resampling.LANCZOS)
        
        # Position (Top Left)
        margin_top = logo_conf.get('margin_top', 40)
        margin_left = logo_conf.get('margin_left', 40)
        
        # x = margin_left
        x = margin_left
        y = margin_top
        
        # Paste using the logo itself as the mask for transparency
        image.paste(logo, (x, y), logo)
        
        return image
        
    except Exception as e:
        logger.error(f"Failed to draw logo: {e}")
        return image
