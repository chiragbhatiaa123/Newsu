import logging
import os
import io
import json
from PIL import Image, ImageDraw

# Import Components
from src.components.colors import get_dominant_color, force_light_color
from src.components.background import prepare_background, create_gradient_overlay
from src.components.footer import draw_footer
from src.components.headline import draw_headline
from src.components.logo import draw_logo

logger = logging.getLogger(__name__)

# Load Config
# Load Config Helpers
CONFIG_PATH = os.path.join(os.getcwd(), 'config', 'template_config.json')

def load_config(user_id=None):
    """Loads config. Prioritizes user specific config if user_id is provided."""
    config = {}
    
    # 1. Load User Config if exists
    if user_id:
        user_conf_path = os.path.join("users_data", str(user_id), "template_config.json")
        if os.path.exists(user_conf_path):
            try:
                with open(user_conf_path, 'r') as f:
                    config = json.load(f)
                return config
            except Exception as e:
                logger.error(f"Failed to load user config for {user_id}: {e}")

    # 2. Fallback to Default
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load default config: {e}")
        
    return config

# We assume TEMPLATE_CONFIG is just a cached default, but we should use load_config(user_id) dynamically
DEFAULT_CONFIG = load_config()

def create_news_image(title, source, date_str, image_url=None, summary=None, manual_image=None, manual_color=None, highlight_text=None, highlight_padding=None, user_id=None):
    """
    Generates a social media image (Vertical 4:5) using modular components.
    manual_image: PIL Image object (optional override for image_url)
    manual_color: RGB tuple or Hex String (optional override)
    user_id: Telegram ID to load specific templates/logos
    highlight_text: Specific string to highlight in the headline
    highlight_padding: Integer px (optional)
    """
    try:
        # Load Config (User or Default)
        cfg = load_config(user_id) if user_id else DEFAULT_CONFIG
        
        width = cfg.get('canvas', {}).get('width', 1080)
        height = cfg.get('canvas', {}).get('height', 1350)
        bg_color = cfg.get('canvas', {}).get('bg_color', [20, 20, 20])
        default_accent = cfg.get('colors', {}).get('accent_default', [0, 120, 215])

        # 1. Background Layer (omitted for brevity, assume same)
        if manual_image:
            # Manually handle resizing for the uploaded object
            bg_img = manual_image.copy()
            # Basic resize to cover
            img_ratio = bg_img.width / bg_img.height
            target_ratio = width / height
            
            if img_ratio > target_ratio:
                scale_height = height
                scale_width = int(scale_height * img_ratio)
                bg_img = bg_img.resize((scale_width, scale_height), Image.Resampling.LANCZOS)
                left = (scale_width - width) // 2
                bg_img = bg_img.crop((left, 0, left + width, height))
            else:
                scale_width = width
                scale_height = int(scale_width / img_ratio)
                bg_img = bg_img.resize((scale_width, scale_height), Image.Resampling.LANCZOS)
                top = (scale_height - height) // 2
                bg_img = bg_img.crop((0, top, width, top + height))
            
            bg_img = bg_img.convert('RGB')
        else:
            bg_img = prepare_background(image_url, width, height, bg_color)
            
        # Determine Color
        dominant_color = None
        if manual_color:
            try:
                if isinstance(manual_color, str) and manual_color.startswith('#'):
                    # Parse Hex
                    h = manual_color.lstrip('#')
                    manual_rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                    dominant_color = force_light_color(manual_rgb)
                elif isinstance(manual_color, tuple):
                    dominant_color = force_light_color(manual_color)
            except Exception:
                logger.error("Failed to parse manual color, falling back.")
        
        if not dominant_color:
             dominant_color = get_dominant_color(bg_img, default_accent)
        
        # 2. Gradient Overlay
        bg_img = bg_img.convert('RGBA')
        overlay = create_gradient_overlay(width, height, cfg)
        bg_img = Image.alpha_composite(bg_img, overlay)
        bg_img = bg_img.convert('RGB')
        
        # 2.5 Logo Layer (On top of gradient)
        bg_img = draw_logo(bg_img, cfg)
        
        draw = ImageDraw.Draw(bg_img)
        
        # 3. Text Components
        summary_text = summary if summary else f"{source} • {date_str}"
        footer_top_y = draw_footer(draw, width, height, summary_text, cfg)
        
        draw_headline(draw, width, footer_top_y, title, dominant_color, cfg, highlight_text=highlight_text, highlight_padding=highlight_padding)
        
        # 4. Save & Archive
        output = io.BytesIO()
        bg_img.save(output, format='PNG')
        output.seek(0)
        
        # Structured Archive Logic
        try:
            from src import gemini_utils
            meta = {
                "title": title,
                "source": source,
                "date": date_str,
                "image_url": "manual_upload" if manual_image else image_url,
                "summary": summary_text,
                "generated_image": "post.png"
            }
            folder = gemini_utils.save_metadata(title, "Manual", meta)
            if folder:
                filepath = os.path.join(folder, "post.png")
                with open(filepath, "wb") as f:
                    f.write(output.getbuffer())
                logger.info(f"Saved image to {filepath}")
        except Exception as e:
            logger.error(f"Archive failed: {e}")
            pass
            
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate image: {e}")
        return None

def create_overlay_image(title, summary, date_str, source="Newsu", manual_color=None, highlight_text=None, highlight_padding=None, user_id=None):
    """
    Generates a Transparent PNG overlay (1080x1920) with just text and logo.
    Used for video generation.
    """
    try:
        # Load Config (User or Default)
        cfg = load_config(user_id) if user_id else DEFAULT_CONFIG
        
        width = cfg.get('canvas', {}).get('width', 1080)
        height = cfg.get('canvas', {}).get('height', 1350)
        
        # Determine Color (Default to Accent if not provided)
        default_accent = cfg.get('colors', {}).get('accent_default', [0, 120, 215])
        dominant_color = None
        
        if manual_color:
             try:
                if isinstance(manual_color, str) and manual_color.startswith('#'):
                     h = manual_color.lstrip('#')
                     manual_rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                     dominant_color = force_light_color(manual_rgb)
             except: pass
             
        if not dominant_color:
            dominant_color = tuple(default_accent)

        # Create Transparent Canvas
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # Add Gradient (Semi-transparent black)
        # We need the gradient to be visible on the video.
        # create_gradient_overlay returns an RGBA image with the gradient.
        # Since overlay is empty, we can just alpha_composite or paste it.
        grad_overlay = create_gradient_overlay(width, height, cfg)
        overlay = Image.alpha_composite(overlay, grad_overlay)
        
        # Draw Logo
        overlay = draw_logo(overlay, cfg)
        
        draw = ImageDraw.Draw(overlay)
        
        # Draw Footer (Summary)
        if summary:
            summary_text = summary
        else:
            parts = [source]
            if date_str: parts.append(date_str)
            summary_text = " • ".join(parts)
            
        footer_top_y = draw_footer(draw, width, height, summary_text, cfg)
        
        # Draw Headline
        draw_headline(draw, width, footer_top_y, title, dominant_color, cfg, highlight_text=highlight_text, highlight_padding=highlight_padding)
        
        # Save
        output = io.BytesIO()
        overlay.save(output, format='PNG')
        output.seek(0)
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate overlay: {e}")
        return None
