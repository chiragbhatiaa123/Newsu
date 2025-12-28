import sys
import os
sys.path.append(os.getcwd())

from src import fetcher
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_extraction():
    # Fetch news to get real links
    print("Fetching news list...")
    items = fetcher.fetch_news_for_unit('india')
    
    if not items:
        print("No news items found.")
        return

    print(f"Found {len(items)} items. Testing first 3 for image extraction...")
    
    for item in items[:3]:
        print(f"\n--- Testing Item: {item['title']} ---")
        print(f"Original Link: {item['link']}")
        
        # Check if fetcher already found one in RSS
        if item.get('image_url'):
            print(f"✅ RSS extracted image: {item['image_url']}")
        else:
            print("❌ No image in RSS payload.")
            
        # Try manual extraction
        print("Attempting manual extraction via get_article_image...")
        extracted_url = fetcher.get_article_image(item['link'])
        
        if extracted_url:
            print(f"✅ Manually extracted: {extracted_url}")
        else:
            print("❌ Manual extraction failed.")

if __name__ == "__main__":
    test_extraction()
