import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src import database as db
from src import fetcher

def test_workflow():
    print("Initializing DB...")
    db.init_db()
    
    print("Testing Fetcher for 'India'...")
    items = fetcher.fetch_news_for_unit('india')
    print(f"Fetched {len(items)} items.")
    
    if not items:
        print("Warning: No items fetched. Internet issue or RSS change?")
        return

    first_item = items[0]
    print(f"First item: {first_item['title']} - {first_item['link']}")
    
    # Test De-duplication
    print("Marking first item as seen...")
    db.mark_news_as_seen(first_item['link'])
    
    print("Checking is_news_seen...")
    if db.is_news_seen(first_item['link']):
        print("PASS: Item marked as seen.")
    else:
        print("FAIL: Item NOT marked as seen.")

    # Test Fetch again - should exclude the seen item
    print("Fetching 'India' again...")
    items_v2 = fetcher.fetch_news_for_unit('india')
    links_v2 = [i['link'] for i in items_v2]
    
    if first_item['link'] not in links_v2:
        print("PASS: De-duplication working. Item excluded.")
    else:
        print("FAIL: Item still in list.")
        
    # Test City Fetch
    print("Testing Fetcher for 'city_Mumbai'...")
    city_items = fetcher.fetch_news_for_unit('city_Mumbai')
    print(f"Fetched {len(city_items)} items for Mumbai.")
    if city_items:
        print(f"First Mumbai item: {city_items[0]['title']}")
    else:
        print("Warning: No items for Mumbai.")

if __name__ == "__main__":
    try:
        test_workflow()
        print("Verification Complete.")
    except Exception as e:
        print(f"Verification Failed: {e}")
