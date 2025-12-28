import requests
import feedparser

URL = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def debug():
    try:
        print(f"Fetching {URL}...")
        response = requests.get(URL, headers=HEADERS, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content Sample: {response.text[:500]}")
        
        feed = feedparser.parse(response.content)
        print(f"Feed Entries: {len(feed.entries)}")
        if feed.bozo:
             print(f"Feed Bozo (Error): {feed.bozo_exception}")
             
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug()
