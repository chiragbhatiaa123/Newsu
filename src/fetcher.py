import requests
import feedparser
import urllib.parse
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from time import mktime
import logging
from src.database import is_news_seen

logger = logging.getLogger(__name__)

# Base Google News RSS URL
BASE_URL = "https://news.google.com/rss"
SEARCH_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

# Unit mapping to specific RSS feeds or queries
UNIT_CONFIG = {
    'global': f"{BASE_URL}?hl=en-IN&gl=IN&ceid=IN:en", # Top stories (Global/General)
    'india': SEARCH_URL.format(query='India'), # India specific - Search is more robust
    'major': f"{BASE_URL}?hl=en-IN&gl=IN&ceid=IN:en", # 'Everything major' -> Top Stories
    # Cities will be handled dynamically
}

def fetch_news_for_unit(unit):
    """
    Fetch news items for a given unit.
    Returns a list of dicts: {'title', 'link', 'published', 'source'}
    """
    url = _get_url_for_unit(unit)
    logger.info(f"Fetching news for unit: {unit} from {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        logger.error(f"Failed to fetch RSS feed: {e}")
        return []
    
    news_items = []
    cutoff_time = datetime.now() - timedelta(hours=48)

    for entry in feed.entries:
        # Deduplication check at fetch time
        if is_news_seen(entry.link):
            continue
        
        # Date filtering (48 hours)
        published_dt = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_dt = datetime.fromtimestamp(mktime(entry.published_parsed))
        
        if published_dt and published_dt < cutoff_time:
            continue
            
        if published_dt and published_dt < cutoff_time:
            continue
            
        # Extract Image URL
        image_url = None
        if 'media_content' in entry and entry.media_content:
             # Look for biggest image
             images = sorted(entry.media_content, key=lambda x: int(x.get('width', 0)), reverse=True)
             if images:
                 candidate = images[0]['url']
                 # Filter out known google news logos/icons
                 if 'google' not in candidate or 'lh3.googleusercontent.com' in candidate: 
                     # Allow lh3 (often hosted images) but maybe filter by size if possible (headers)
                     # But definitely filter out small icons if width < 300
                     if int(images[0].get('width', 0)) > 400:
                        image_url = candidate

        # Extract Summary/Description
        summary_text = ""
        if 'description' in entry:
            try:
                soup = BeautifulSoup(entry.description, 'html.parser')
                summary_text = soup.get_text(separator=' ', strip=True)
                # Fallback image extraction from description if main check failed
                if not image_url:
                    img_tag = soup.find('img')
                    if img_tag and img_tag.get('src'):
                        candidate = img_tag['src']
                        if 'google' not in candidate or 'proxy' in candidate:
                            image_url = candidate
            except Exception:
                pass

        item = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.published,
            'source': entry.source.title if 'source' in entry else 'Google News',
            'image_url': image_url,
            'summary': summary_text
        }
        news_items.append(item)
        
    logger.info(f"Found {len(news_items)} new items for {unit} (Last 48 hours)")
    return news_items

def _get_url_for_unit(unit):
    unit = unit.lower().strip()
    
    if unit in UNIT_CONFIG:
        return UNIT_CONFIG[unit]
    
    if unit.startswith('city_'):
        city_name = unit.replace('city_', '').replace('_', ' ')
        encoded_query = urllib.parse.quote(city_name)
        return SEARCH_URL.format(query=encoded_query)
        
    # Default to major/global if unknown
    return UNIT_CONFIG['major']

def get_article_image(url):
    """
    Scrapes the og:image from the article URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Follow redirects (often RSS links are redirects)
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Try og:image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
            
            # Try twitter:image
            tw_image = soup.find('meta', name='twitter:image')
            if tw_image and tw_image.get('content'):
                return tw_image['content']
                
    except Exception as e:
        logger.error(f"Failed to fetch article image for {url}: {e}")
    
    return None

def scrape_url_metadata(url):
    """
    Scrapes metadata (Title, Description, Image) from a direct news link.
    Returns a dict consistent with specific news items.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Title
        title = None
        if soup.find('meta', property='og:title'):
            title = soup.find('meta', property='og:title')['content']
        elif soup.title:
            title = soup.title.string
            
        # Remove site name often in title (e.g. "News Title - BBC")
        if title:
            params = title.split(' - ')
            if len(params) > 1: title = params[0]
            params = title.split(' | ')
            if len(params) > 1: title = params[0]
            
        # Description / Summary
        summary = ""
        if soup.find('meta', property='og:description'):
            summary = soup.find('meta', property='og:description')['content']
        elif soup.find('meta', name='description'):
            summary = soup.find('meta', name='description')['content']
            
        # Image
        image_url = None
        if soup.find('meta', property='og:image'):
            image_url = soup.find('meta', property='og:image')['content']
        elif soup.find('meta', name='twitter:image'):
            image_url = soup.find('meta', name='twitter:image')['content']
            
        if not title:
            return None
            
        from datetime import datetime
        return {
            'title': title.strip(),
            'link': url,
            'published': datetime.now().strftime("%d %b, %Y"), # Current time as proxy
            'source': urllib.parse.urlparse(url).netloc.replace('www.', ''),
            'image_url': image_url,
            'summary': summary.strip(),
            'content': '' # Fallback
        }
        
        # Extended Text Scraping (for better Gemini Context)
        try:
            paragraphs = soup.find_all('p')
            text_content = " ".join([p.get_text().strip() for p in paragraphs])
            # Limit to 3000 chars to avoid token limits
            data['content'] = text_content[:3000].strip() or summary.strip()
        except Exception:
            data['content'] = summary.strip()
            
        return data
        
    except Exception as e:
        logger.error(f"Scrape URL failed: {e}")
        return None
