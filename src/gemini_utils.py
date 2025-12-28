from google import genai
import logging
import os
import re # Added import for re module
from src.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Common Indian News Sources to strip
SOURCE_BLACKLIST = [
    "NDTV", "Times of India", "TOI", "Hindustan Times", "The Hindu", 
    "Indian Express", "LiveMint", "Moneycontrol", "News18", "India Today", 
    "Business Standard", "Economic Times", "Mint", "Zee News"
]

def clean_text(text):
    """Removes known source names from text."""
    for source in SOURCE_BLACKLIST:
        # Case insensitive replace of source name WITH WORD BOUNDARIES
        # prevents stripping "Mint" from "Commitment" etc.
        pattern = re.compile(r'\b' + re.escape(source) + r'\b', re.IGNORECASE)
        text = pattern.sub("", text)
    
    # Strip trailing periods as per user request
    text = text.rstrip('.')
    return text

def generate_copy(title, source):
    """
    Generates viral social media copy using Gemini.
    """
    if not GEMINI_API_KEY:
        return "Gemini API Key missing. Check .env"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        Act as a social media news manager. 
        Write a short, engaging 3-line copy for this news headline:
        "{title}"
        
        Rules:
        1. Catchy first line.
        2. Informative second line.
        3. Hashtags or call to action in third line.
        4. No emojis at start of lines.
        5. NEVER mention source names.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        text = response.text.strip()
        
        # Strict Cleaning
        text = clean_text(text)
        
        return text
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return "Sorry, I couldn't generate the copy right now."

def generate_one_liner(title, context_text="", style="Simple"):
    """Generates a short <12 words summary for the image footer."""
    if not GEMINI_API_KEY:
        return "Breaking News"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        context_block = ""
        if context_text and len(context_text) > 10:
            context_block = f"\nNews Context/Details: {context_text}\n"
            
        style_instruction = "Tone: Informative, objective, simple English (NO opinion)."
        if style.lower() == 'professional':
            style_instruction = "Tone: Formal, objective, authoritative journalistic standard."
        elif style.lower() == 'narrative':
            style_instruction = "Tone: Story-telling, engaging, setting the scene."
        elif style.lower() == 'casual':
            style_instruction = "Tone: Witty, conversational, social media slang allowed."
            
        prompt = f"""
        Write a short, detailed subheading for this news.
        - Rules:
            1. Find the REASON or KEY DETAIL in the context.
            2. Do NOT repeat what is already in the Headline.
            3. {style_instruction}
            4. Length: 5-10 words.
            5. NO periods at the end.
            6. Just give the output, no choices.
        
        Headline: '{title}'
        {context_block}
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        text = response.text.strip().replace('"', '')
        return clean_text(text)
    except Exception:
        return "Latest Update"

def refine_headline(title, style="Simple"):
    """
    Refines the raw RSS headline for social media.
    Styles: Professional, Narrative, Simple, Casual.
    """
    if not GEMINI_API_KEY:
        return title 
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        style_prompt = "Style: Simple, casual, easy to understand."
        if style.lower() == 'professional':
            style_prompt = "Style: Formal, precise, executive summary style."
        elif style.lower() == 'narrative':
            style_prompt = "Style: Compelling, story-driven, emotional hook."
        elif style.lower() == 'casual':
            style_prompt = "Style: Catchy, witty, viral social media style (Gen Z friendly)."
        
        prompt = f"""
        Refine this headline into a {style} news update.
        
        Input: "{title}"
        
        Rules:
        1. Keep it SHORT (12-15 words max).
        2. KEEP specific names, places, and numbers.
        3. {style_prompt}
        4. QUOTES: Put the quote FIRST, then the speaker.
        5. Return ONLY the refined text.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        text = response.text.strip().replace('"', '')
        return clean_text(text)
    except Exception as e:
        logger.error(f"Headline refinement failed: {e}")
        return title

def generate_all_variations(title, context_text=""):
    """Generates 4 variations of Headline+Subheading in one go."""
    if not GEMINI_API_KEY:
        return {}
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        I need 4 different styles of Social Media updates for this news.
        
        Headline: "{title}"
        Context: "{context_text[:500]}"
        
        Styles:
        1. Professional: Formal, executive summary.
        2. Narrative: Story-telling, engaging.
        3. Simple: Direct, 5-year-old understandable.
        4. Casual: Witty, social media vibes.
        
        Format your response strictly as JSON:
        {{
            "Professional": {{ "headline": "...", "sub": "..." }},
            "Narrative": {{ "headline": "...", "sub": "..." }},
            "Simple": {{ "headline": "...", "sub": "..." }},
            "Casual": {{ "headline": "...", "sub": "..." }}
        }}
        
        Rules:
        - Headlines: Max 12 words.
        - Subheadings: Max 8 words, no periods.
        - No Source Names.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        import json
        text = response.text.strip()
        
        # Cleanup Markdown Code Blocks if present
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"JSON Parse Error. Raw Text: {text}")
            return {}
            
    except Exception as e:
        logger.error(f"Variation generation failed: {e}")
        return {}

def verify_image_usability(image_url, related_headline=None):
    """
    Uses Gemini Vision to check if an image is suitable for a news background.
    If related_headline is provided, checks if the image matches the topic.
    """
    if not GEMINI_API_KEY or not image_url:
        return False
        
    try:
        # We need the image data
        import requests
        from PIL import Image
        import io
        
        # Robust Headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        try:
            resp = requests.get(image_url, headers=headers, timeout=10)
        except Exception as e:
            logger.warning(f"Download Error for {image_url}: {e}")
            return False

        if resp.status_code != 200:
            logger.warning(f"Image download failed {resp.status_code}: {image_url}")
            return False
        
        content_len = len(resp.content)
        content_type = resp.headers.get('Content-Type', '')
        logger.info(f"Downloaded {content_len} bytes. Type: {content_type}")
        
        # 1. Technical Validation
        if content_len < 5500: # 5.5KB limit (Gradient is ~40KB, but small icons are <2KB)
            logger.warning(f"Rejecting: File too small ({content_len} bytes)")
            return False
            
        if 'text/html' in content_type.lower():
            logger.warning("Rejecting: Content is HTML")
            return False

        try:
            image_part = Image.open(io.BytesIO(resp.content))
            width, height = image_part.size
            if width < 250 or height < 200:
                logger.warning(f"Rejecting: Dimensions too small ({width}x{height})")
                return False
        except Exception as e:
            logger.warning(f"Rejecting: Invalid Image Data - {e}")
            return False
            
        # 2. Analyze with Gemini (Visual Verification)
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # visual context check
        context_prompt = ""
        if related_headline:
            context_prompt = f"3. RELEVANCE: Is this image related to the news headline: '{related_headline}'? If it's a generic unrelated stock photo or completely wrong topic, Answer NO."
            
        prompt = f"""
        Analyze this image for a news background.
        
        Checks:
        1. QUALITY: Is it blurry, too small, or pixelated?
        2. CONTENT: Is it just a logo, a block of text, or a generic graphic?
        {context_prompt}
        
        Answer ONLY "YES" if it is good and relevant. 
        Answer "NO [Reason]" if it fails.
        
        NOTE: Maps, Charts, and Infographics are ACCEPTABLE if relevant.
        NOTE: Generic photos (e.g. Traffic for 'Traffic Jam', Smog for 'Pollution') are ACCEPTABLE.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=[prompt, image_part]
        )
        
        clean_resp = response.text.upper().strip()
        logger.info(f"Vision Verification for '{related_headline or 'Image'}': {clean_resp}")
        
        return "YES" in clean_resp
        
    except Exception as e:
        logger.error(f"Vision verification failed: {e}")
        return False

def save_metadata(title, source, data_dict):
    """Saves metadata to the structured workspace."""
    try:
        from datetime import datetime
        import json
        
        now = datetime.now()
        date_folder = now.strftime("%Y-%m-%d")
        safe_title = re.sub(r'[^\w\-_\. ]', '_', title)[:50].strip()
        
        folder_path = os.path.join("workspace", date_folder, safe_title)
        os.makedirs(folder_path, exist_ok=True)
        
        # Save Metadata
        meta_path = os.path.join(folder_path, "metadata.json")
        
        # Update existing or create new
        existing = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except: pass
            
        existing.update(data_dict)
        existing['last_updated'] = now.isoformat()
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
            
        return folder_path
    except Exception as e:
        logger.error(f"Metadata save failed: {e}")
        return None
