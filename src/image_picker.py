
import logging
import random
from src import image_searcher

logger = logging.getLogger(__name__)

class ImagePicker:
    def __init__(self, query):
        self.query = query
        self.seen_urls = set()
        self.cached_images = []
        self.page = 0
        
    async def fetch_next_batch(self, count=5):
        """
        Fetches the next batch of unique images.
        Mixes generic Google Images and Pinterest results.
        """
        candidates = []
        attempts = 0
        
        # We need to loop until we have enough unique candidates
        # or we run out of reasonable attempts to avoid infinite loops
        while len(candidates) < count and attempts < 3:
            attempts += 1
            
            # Strategy:
            # Page 0: Mix of Standard + Pinterest
            # Page 1+: Dig deeper
            
            # Fetch Generic
            new_generic = image_searcher.search_google_images(
                self.query, 
                offset=self.page * 10
            ) or []
            
            # Fetch Pinterest (Explicitly add 'site:pinterest.com')
            new_pinterest = image_searcher.search_google_images(
                f"{self.query} site:pinterest.com", 
                offset=self.page * 10
            ) or []
            
            # Interleave them for variety: [Gen, Pin, Gen, Pin...]
            mixed = []
            max_len = max(len(new_generic), len(new_pinterest))
            for i in range(max_len):
                if i < len(new_generic): mixed.append(new_generic[i])
                if i < len(new_pinterest): mixed.append(new_pinterest[i])
            
            # Filter duplicates
            for url in mixed:
                if url not in self.seen_urls and url not in candidates:
                    candidates.append(url)
                    self.seen_urls.add(url)
                    self.cached_images.append(url)
                    
                    if len(candidates) >= count:
                        break
            
            self.page += 1
            
        return candidates[:count]

    def get_image_at_index(self, index):
        """Returns the image URL at a specific global index (0-based)"""
        if 0 <= index < len(self.cached_images):
            return self.cached_images[index]
        return None
