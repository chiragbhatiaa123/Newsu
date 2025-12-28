import os
import logging
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)

def search_google_images(query, offset=0):
    """
    Searches for high-quality images using SerpApi (Google Images).
    Returns the first usable image URL.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        logger.warning("SERPAPI_KEY not found. Skipping image search.")
        return None
        
    
    # 1. Try Large Images First
    logger.info(f"Searching SerpApi (Large) for: '{query}'")
    params = {
        "q": query,
        "tbm": "isch",
        "ijn": str(offset // 10), # Approximation: 10 results per page usually, ijn is page index
        "api_key": api_key,
        "tbs": "isz:l", # Large images
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        images = results.get("images_results", [])
        
        if images:
            # Filter out unusable domains
            blacklisted_domains = ['instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'youtube.com']
            
            clean_candidates = []
            for img in images:
                url = img.get("original")
                if not url:
                    continue
                    
                if any(domain in url.lower() for domain in blacklisted_domains):
                    continue
                    
                clean_candidates.append(url)
                if len(clean_candidates) >= 5: # Get top 5 valid candidates
                    break
            
            logger.info(f"Found {len(clean_candidates)} valid large images (filtered from {len(images)}).")
            return clean_candidates
            
        logger.warning("No large images found. Retrying with Medium...")
        
        # 2. Fallback to Medium (Relaxed Size)
        params["tbs"] = "isz:m"
        search = GoogleSearch(params)
        results = search.get_dict()
        images = results.get("images_results", [])
        
        if images:
            blacklisted_domains = ['instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'youtube.com']
            clean_candidates = []
            for img in images:
                url = img.get("original")
                if not url: continue
                if any(domain in url.lower() for domain in blacklisted_domains): continue
                clean_candidates.append(url)
                if len(clean_candidates) >= 5: break
                
            logger.info(f"Found {len(clean_candidates)} valid medium images.")
            return clean_candidates
            
        logger.warning("No medium images found. Retrying with Any size...")
        
        # 3. Fallback to Any Size
        del params["tbs"]
        search = GoogleSearch(params)
        results = search.get_dict()
        images = results.get("images_results", [])
        
        if images:
            blacklisted_domains = ['instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'youtube.com']
            clean_candidates = []
            for img in images:
                url = img.get("original")
                if not url: continue
                if any(domain in url.lower() for domain in blacklisted_domains): continue
                clean_candidates.append(url)
                if len(clean_candidates) >= 5: break

            logger.info(f"Found {len(clean_candidates)} valid images (any size).")
            return clean_candidates
            
        logger.warning("No images found at all.")
        return []

    except Exception as e:
        logger.error(f"SerpApi search failed details: {e}")
        return []
