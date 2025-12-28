from PIL import ImageDraw, ImageFont
import textwrap

def draw_headline(draw, width, reference_y, text, dominant_color, config, highlight_text=None, highlight_padding=None):
    """
    Draws the headline.
    """
    cfg_fonts = config.get('fonts', {})
    cfg_layout = config.get('layout', {})
    cfg_colors = config.get('colors', {})
    
    # Layout Params
    safe_margin = cfg_layout.get('safe_zone_margin', 50)
    
    # Dynamic Padding Logic
    # Default is 4px (Tight) now based on recent feedback "reduce breath"
    # But user can override via highlight_padding
    if highlight_padding is not None:
        padding_x = int(highlight_padding)
        # Scale Y padding to be about 60% of X or min 2
        padding_y_box = max(2, int(padding_x * 0.6))
    else:
        padding_x = 3 # Default 3px as requested
        padding_y_box = 1 # Tighter Y for 3px X
        
    max_width = width - (safe_margin * 2) - (padding_x * 2)
    center_x = width // 2
    
    # ... (rest of logic same until drawing) ...

    # Font Params
    start_size = cfg_fonts.get('headline_size_start', 65)
    min_size = cfg_fonts.get('headline_size_min', 35)
    font_path = cfg_fonts.get('headline_path', 'arialbd.ttf')
    
    # Identify Highlighted Word Indices
    words = text.split()
    highlight_indices = set()
    
    if highlight_text:
        # User defines END point... (Logic preserved)
        clean_full = [w.lower().replace('.', '').replace(',', '') for w in words]
        clean_target = highlight_text.lower().replace('.', '').replace(',', '').split()
        
        if clean_target:
            n = len(clean_target)
            end_index = -1
            for i in range(len(clean_full) - n + 1):
                if clean_full[i : i+n] == clean_target:
                    end_index = i + n - 1
                    break
            if end_index == -1 and n == 1:
                 try:
                     end_index = clean_full.index(clean_target[0])
                 except ValueError:
                     pass
            if end_index != -1:
                for k in range(end_index + 1):
                    highlight_indices.add(k)
                    
    else:
        # Legacy: Will highlight Line 0 later
        pass

    # Dynamic Sizing & Wrapping Loop
    final_font = None
    final_lines = [] 
    current_size = start_size
    
    while current_size >= min_size:
        try:
            font = ImageFont.truetype(font_path, current_size)
        except OSError:
            font = ImageFont.load_default()
            break
            
        space_w = draw.textlength(" ", font=font)
        
        lines = []
        current_line = []
        current_line_w = 0
        all_fits = True
        
        current_word_idx = 0
        
        for w_str in words:
            w_w = draw.textlength(w_str, font=font)
            added_w = w_w + (space_w if current_line else 0)
            
            if current_line_w + added_w <= max_width:
                current_line.append({'text': w_str, 'w': w_w, 'idx': current_word_idx})
                current_line_w += added_w
            else:
                if not current_line: 
                    all_fits = False 
                    break 
                
                lines.append(current_line)
                current_line = [{'text': w_str, 'w': w_w, 'idx': current_word_idx}]
                current_line_w = w_w
                
            current_word_idx += 1
            
        if current_line:
            lines.append(current_line)
            
        if all_fits and len(lines) <= 4:
            final_lines = lines
            final_font = font
            break
            
        current_size -= 4 
        
    if not final_font:
        if not final_lines: 
            final_font = ImageFont.load_default()
            final_lines = [[{'text': w, 'w': 10, 'idx': i} for i, w in enumerate(words)]]
    
    # Calculate Heights
    ascent, descent = final_font.getmetrics()
    line_height = ascent + descent
    line_spacing = cfg_layout.get('element_spacing_y', 8)
    total_text_height = len(final_lines) * line_height + (len(final_lines)-1) * line_spacing
    
    # Drawing Params for Box
    box_offset = 0    
    
    gap = cfg_layout.get('headline_summary_gap', 100)
    start_y = reference_y - total_text_height - gap
    current_y = start_y
    
    text_color_main = tuple(cfg_colors.get('text_headline_body', [255,255,255]))
    text_color_box = tuple(cfg_colors.get('text_headline_box', [0,0,0]))
    
    for line_idx, line_words in enumerate(final_lines):
        lw = sum(item['w'] for item in line_words) + (len(line_words)-1) * space_w
        start_x = center_x - (lw / 2)
        
        is_legacy_highlight = (highlight_text is None) and (line_idx == 0)
        current_x = start_x
        
        # Pre-pass: Draw Boxes
        ranges = []
        if is_legacy_highlight:
            ranges.append((0, len(line_words)-1))
        else:
            in_range = False
            start_i = -1
            for i, item in enumerate(line_words):
                is_hi = item['idx'] in highlight_indices
                if is_hi and not in_range:
                    in_range = True
                    start_i = i
                elif not is_hi and in_range:
                    in_range = False
                    ranges.append((start_i, i-1))
            if in_range:
                ranges.append((start_i, len(line_words)-1))
        
        for r_start, r_end in ranges:
            px_start = start_x + sum(w['w'] + space_w for w in line_words[:r_start])
            width_range = sum(w['w'] + space_w for w in line_words[r_start:r_end+1]) - space_w
            px_end = px_start + width_range
            
            box_x0 = px_start - padding_x
            box_y0 = current_y - padding_y_box
            box_x1 = px_end + padding_x
            box_y1 = current_y + line_height + padding_y_box + box_offset
            
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=dominant_color)
            
        # Draw Text
        curr_word_x = start_x
        for i, item in enumerate(line_words):
            
            # Determine Color
            use_box_color = False
            if is_legacy_highlight:
                use_box_color = True
            elif item['idx'] in highlight_indices:
                use_box_color = True
                
            fill = text_color_box if use_box_color else text_color_main
            
            draw.text((curr_word_x, current_y), item['text'], font=final_font, fill=fill)
            
            curr_word_x += item['w'] + space_w
            
        current_y += line_height + line_spacing
