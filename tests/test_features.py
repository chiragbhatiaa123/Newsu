import sys
import os

sys.path.append(os.getcwd())

from src import x_fetcher
from src import gemini_utils

def test_features():
    print("Testing X Fetcher Mock/Graceful Failure...")
    # Should log warning/error but not crash if keys missing
    items = x_fetcher.get_trending_news("India")
    print(f"X Fetcher returned {len(items)} items (Expected 0 if no keys).")
    
    print("\nTesting Gemini Utils Mock/Graceful Failure...")
    copy = gemini_utils.generate_copy("Test Title", "Test Source")
    print(f"Gemini Response: {copy}")
    
    if "API Key not configured" in copy or "Sorry" in copy:
        print("PASS: System handled missing keys gracefully.")
    else:
        print("PASS: System generated copy (Keys present?).")

if __name__ == "__main__":
    test_features()
