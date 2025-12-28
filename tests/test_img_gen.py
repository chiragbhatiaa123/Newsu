import sys
import os

sys.path.append(os.getcwd())

from src import image_generator

def test_gen():
    print("Testing Image Generation...")
    output = image_generator.create_news_image(
        "Breaking: Artificial Intelligence Solves P=NP Problem in 5 Minutes", 
        "Tech Daily", 
        "2025-12-23T10:00:00Z"
    )
    
    if output and output.getbuffer().nbytes > 0:
        print(f"PASS: Image generated successfully ({output.getbuffer().nbytes} bytes).")
    else:
        print("FAIL: Image generation returned empty or None.")

if __name__ == "__main__":
    test_gen()
