from PIL import ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)

def draw_footer(draw, image_width, image_height, text, config):
    """
    Draws the summary/subheading on the image.
    Returns the Y position where the footer text starts (for relative positioning).
    """
    sub_cfg = config.get('subheading', {})
    
    # Load Font
    try:
        font = ImageFont.truetype(sub_cfg.get('font_path', 'arial.ttf'), sub_cfg.get('font_size', 35))
    except OSError:
        font = ImageFont.load_default()
        
    color = tuple(sub_cfg.get('color', [200, 200, 200]))
    margin_bottom = sub_cfg.get('margin_bottom', 120)
    # Prefer specific subheading margin, else fall back to global safe zone
    safe_margin = sub_cfg.get('margin_x', config.get('layout', {}).get('safe_zone_margin', 50))
    
    # Calculate Max Width
    max_width = image_width - (safe_margin * 2)
    
    # Wrap Text
    import textwrap
    chars_limit = int(max_width / (sub_cfg.get('font_size', 35) * 0.5))
    wrapper = textwrap.TextWrapper(width=chars_limit)
    lines = wrapper.wrap(text)
    
    # Draw Lines (Centered)
    # Start drawing at footer_y. If multiple lines, we might need to adjust logic, 
    # but for now let's draw downwards from the margin point.
    
    current_y = image_height - margin_bottom
    line_spacing = config.get('layout', {}).get('element_spacing_y', 8)
    
    # If multiple lines, maybe we want to grow UPWARDS so the bottom margin stays fixed?
    # But current logic seems to be "margin from bottom to START of text".
    # Let's stick to that for consistency, or else the headline might overlap if we grow up.
    # Actually, if we grow down, we might hit edge.
    # Let's assume margin_bottom is "space reserved at bottom", so text should basically end near there?
    # No, usually "margin bottom" implies distance from bottom edge to element.
    # The existing code did `footer_y = h - margin`. So text starts there and goes down.
    # If I wrap, I continue going down.
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (image_width - text_width) // 2
        
        draw.text((x, current_y), line, font=font, fill=color)
        current_y += text_height + line_spacing
        
    logger.info(f"Drew footer wrapped ({len(lines)} lines)")
    
    # Return the TOP of the footer so headline can stack above it
    return image_height - margin_bottom
