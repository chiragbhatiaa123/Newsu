from PIL import Image
import logging

logger = logging.getLogger(__name__)

def get_dominant_color(image, default_color):
    """
    Extracts the dominant color from the image.
    Uses quantization to find the most common color palette.
    """
    try:
        # Resize to speed up processing
        small_img = image.copy().resize((150, 150))
        # Reduce to 5 colors (P mode)
        result = small_img.convert('P', palette=Image.ADAPTIVE, colors=5)
        
        # Get palette
        palette = result.getpalette()
        color_counts = sorted(result.getcolors(), reverse=True)
        
        # Get most common color
        if color_counts:
            # Try to find a naturally light color first
            for count, index in color_counts:
                r, g, b = palette[index*3 : index*3 + 3]
                if is_light((r, g, b)):
                    logger.info(f"Found naturally light dominant color: {(r, g, b)}")
                    return (r, g, b)
            
            # If no light color found, pick the most dominant and force lighten it
            palette_index = color_counts[0][1]
            dominant = palette[palette_index*3 : palette_index*3 + 3]
            return force_light_color(tuple(dominant))
            
        return force_light_color(tuple(default_color))
    except Exception as e:
        logger.error(f"Color extraction failed: {e}")
        return force_light_color(tuple(default_color))

def is_light(rgb):
    """Check if color is light enough for black text."""
    r, g, b = rgb
    # Luminance formula
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return luminance > 200 # Threshold raised for max visibility

def force_light_color(rgb):
    """Mix with white until light enough."""
    r, g, b = rgb
    while not is_light((r, g, b)):
        # Lighten aggressively (50% mix)
        r = int(r * 0.5 + 255 * 0.5)
        g = int(g * 0.5 + 255 * 0.5)
        b = int(b * 0.5 + 255 * 0.5)
        if r > 250 and g > 250 and b > 250: # Avoid pure white if possible, but safety cap
            break
            
    return (r, g, b)

# --- HTML Color Database ---
HTML_COLORS = {
    'indianred': '#CD5C5C', 'lightcoral': '#F08080', 'salmon': '#FA8072', 'darksalmon': '#E9967A',
    'lightsalmon': '#FFA07A', 'crimson': '#DC143C', 'red': '#FF0000', 'firebrick': '#B22222',
    'darkred': '#8B0000', 'pink': '#FFC0CB', 'lightpink': '#FFB6C1', 'hotpink': '#FF69B4',
    'deeppink': '#FF1493', 'mediumvioletred': '#C71585', 'palevioletred': '#DB7093',
    'coral': '#FF7F50', 'tomato': '#FF6347', 'orangered': '#FF4500', 'darkorange': '#FF8C00',
    'orange': '#FFA500', 'gold': '#FFD700', 'yellow': '#FFFF00', 'lightyellow': '#FFFFE0',
    'lemonchiffon': '#FFFACD', 'lightgoldenrodyellow': '#FAFAD2', 'papayawhip': '#FFEFD5',
    'moccasin': '#FFE4B5', 'peachpuff': '#FFDAB9', 'palegoldenrod': '#EEE8AA', 'khaki': '#F0E68C',
    'darkkhaki': '#BDB76B', 'lavender': '#E6E6FA', 'thistle': '#D8BFD8', 'plum': '#DDA0DD',
    'violet': '#EE82EE', 'orchid': '#DA70D6', 'fuchsia': '#FF00FF', 'magenta': '#FF00FF',
    'mediumorchid': '#BA55D3', 'mediumpurple': '#9370DB', 'rebeccapurple': '#663399',
    'blueviolet': '#8A2BE2', 'darkviolet': '#9400D3', 'darkorchid': '#9932CC', 'darkmagenta': '#8B008B',
    'purple': '#800080', 'indigo': '#4B0082', 'slateblue': '#6A5ACD', 'darkslateblue': '#483D8B',
    'mediumslateblue': '#7B68EE', 'greenyellow': '#ADFF2F', 'chartreuse': '#7FFF00',
    'lawngreen': '#7CFC00', 'lime': '#00FF00', 'limegreen': '#32CD32', 'palegreen': '#98FB98',
    'lightgreen': '#90EE90', 'mediumspringgreen': '#00FA9A', 'springgreen': '#00FF7F',
    'mediumseagreen': '#3CB371', 'seagreen': '#2E8B57', 'forestgreen': '#228B22', 'green': '#008000',
    'darkgreen': '#006400', 'yellowgreen': '#9ACD32', 'olivedrab': '#6B8E23', 'olive': '#808000',
    'darkolivegreen': '#556B2F', 'mediumaquamarine': '#66CDAA', 'darkseagreen': '#8FBC8B',
    'lightseagreen': '#20B2AA', 'darkcyan': '#008B8B', 'teal': '#008080', 'aqua': '#00FFFF',
    'cyan': '#00FFFF', 'lightcyan': '#E0FFFF', 'paleturquoise': '#AFEEEE', 'aquamarine': '#7FFFD4',
    'turquoise': '#40E0D0', 'mediumturquoise': '#48D1CC', 'darkturquoise': '#00CED1',
    'cadetblue': '#5F9EA0', 'steelblue': '#4682B4', 'lightsteelblue': '#B0C4DE', 'powderblue': '#B0E0E6',
    'lightblue': '#ADD8E6', 'skyblue': '#87CEEB', 'lightskyblue': '#87CEFA', 'deepskyblue': '#00BFFF',
    'dodgerblue': '#1E90FF', 'cornflowerblue': '#6495ED', 'royalblue': '#4169E1', 'blue': '#0000FF',
    'mediumblue': '#0000CD', 'darkblue': '#00008B', 'navy': '#000080', 'midnightblue': '#191970',
    'cornsilk': '#FFF8DC', 'blanchedalmond': '#FFEBCD', 'bisque': '#FFE4C4', 'navajowhite': '#FFDEAD',
    'wheat': '#F5DEB3', 'burlywood': '#DEB887', 'tan': '#D2B48C', 'rosybrown': '#BC8F8F',
    'sandybrown': '#F4A460', 'goldenrod': '#DAA520', 'darkgoldenrod': '#B8860B', 'peru': '#CD853F',
    'chocolate': '#D2691E', 'saddlebrown': '#8B4513', 'sienna': '#A0522D', 'brown': '#A52A2A',
    'maroon': '#800000', 'white': '#FFFFFF', 'snow': '#FFFAFA', 'honeydew': '#F0FFF0',
    'mintcream': '#F5FFFA', 'azure': '#F0FFFF', 'aliceblue': '#F0F8FF', 'ghostwhite': '#F8F8FF',
    'whitesmoke': '#F5F5F5', 'seashell': '#FFF5EE', 'beige': '#F5F5DC', 'oldlace': '#FDF5E6',
    'floralwhite': '#FFFAF0', 'ivory': '#FFFFF0', 'antiquewhite': '#FAEBD7', 'linen': '#FAF0E6',
    'lavenderblush': '#FFF0F5', 'mistyrose': '#FFE4E1', 'gainsboro': '#DCDCDC', 'lightgray': '#D3D3D3',
    'silver': '#C0C0C0', 'darkgray': '#A9A9A9', 'gray': '#808080', 'dimgray': '#696969',
    'lightslategray': '#778899', 'slategray': '#708090', 'darkslategray': '#2F4F4F', 'black': '#000000'
}

import difflib

def parse_color_name(input_str):
    """
    Tries to find a hex code for the input string.
    1. Exact match (case insensitive)
    2. Fuzzy match
    Returns (hex_code, name_found) or (None, None)
    """
    clean_input = input_str.lower().replace(" ", "")
    
    # 1. Exact Match
    if clean_input in HTML_COLORS:
        return HTML_COLORS[clean_input], clean_input
        
    # 2. Fuzzy Match
    matches = difflib.get_close_matches(clean_input, HTML_COLORS.keys(), n=1, cutoff=0.6)
    if matches:
        return HTML_COLORS[matches[0]], matches[0]
        
    return None, None
