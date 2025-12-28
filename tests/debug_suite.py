import argparse
import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from src import database as db
from src import fetcher
from src import x_fetcher
from src import gemini_utils
from src import image_generator
from src import image_searcher # Added import
from src.utils.logger import setup_logger

# Setup logging for the test run
setup_logger()
logger = logging.getLogger("DebugSuite")

def test_fetch():
    logger.info("=== Testing News Fetcher ===")
    items = fetcher.fetch_news_for_unit('india')
    logger.info(f"Fetched {len(items)} items.")
    for item in items[:3]:
        print(f"- {item['title']} ({item['published']})")

def test_db():
    logger.info("=== Testing Database ===")
    db.init_db()
    users = db.get_all_users()
    logger.info(f"Existing Users: {len(users)}")
    print(users)

def test_x():
    logger.info("=== Testing X Fetcher ===")
    items = x_fetcher.get_trending_news('India')
    logger.info(f"Fetched {len(items)} tweets.")
    for item in items[:3]:
        print(f"🐦 {item['title']}")

def test_gemini():
    logger.info("=== Testing Gemini ===")
    copy = gemini_utils.generate_copy("Test News Headline", "Test Source")
    print(f"Generated Copy:\n{copy}")

def test_image():
    logger.info("=== Testing Image Gen ===")
    
    logger.info("Fetching real news items from 'Pune' unit...")
    items = fetcher.fetch_news_for_unit('city_Pune')
    
    target_item = None
    match_count = 0
    for item in items:
        # Check filtered image_url
        if item.get('image_url'):
            match_count += 1
            if match_count == 3: # Pick the 3rd one for variety
                target_item = item
                logger.info(f"Using (3rd) image from fetcher: {item['image_url']}")
                break
                
    if not target_item and items:
        target_item = items[0]
        logger.warning("No item with image_url found, using first item to test fallback/gradient.")
        manual_url = fetcher.get_article_image(target_item['link'])
        if manual_url:
            target_item['image_url'] = manual_url
            logger.info(f"Manual fetch success: {manual_url}")
        else:
             logger.warning("Manual fetch failed too.")
        
    if target_item:
        logger.info(f"Generating image for: {target_item['title']}")
        
        # Test Refinement
        refined_title = gemini_utils.refine_headline(target_item['title'])
        logger.info(f"Refined Title: '{refined_title}'")
        
        # Test Image: Enforce SERP ONLY & Relevance Check (Multi-Candidate)
        logger.info("Testing Image Search (SERP Only) + Relevance Check...")
        candidates = image_searcher.search_google_images(refined_title)
        
        final_image_url = None
        if candidates:
            logger.info(f"Found {len(candidates)} candidates.")
            for idx, url in enumerate(candidates):
                logger.info(f"Verifying Candidate {idx+1}: {url}")
                is_good = gemini_utils.verify_image_usability(url, related_headline=refined_title)
                if is_good:
                    final_image_url = url
                    logger.info("Candidate Accepted!")
                    break
                else:
                    logger.warning("Candidate Rejected.")
        else:
            logger.warning("SERP Search failed (No candidates). Using Gradient.")
            
        logger.info(f"Final Image URL: {final_image_url}")
        
        # Generator flow
        summary_text = gemini_utils.generate_one_liner(refined_title)
        summary_text = gemini_utils.clean_text(summary_text) 
        
        logger.info(f"Summary: {summary_text}")
        
        img = image_generator.create_news_image(
            refined_title, 
            target_item['source'], 
            target_item['published'], # Use real date
            image_url=final_image_url,
            summary=summary_text
        )
        if img:
            print(f"Image generated successfully: {img.getbuffer().nbytes} bytes")
        else:
            print("Image generation failed.")
    else:
        print("No news items found to test.")

def test_multi():
    logger.info("=== Testing Multiple Cities (Stress Test) ===")
    cities = ['city_Delhi', 'city_Mumbai', 'city_Kolkata', 'city_Chennai', 'city_Bangalore']
    
    results = {}
    
    for city in cities:
        logger.info(f"\n>>> TESTING UNIT: {city}")
        try:
            items = fetcher.fetch_news_for_unit(city)
            if not items:
                logger.warning(f"No items found for {city}")
                results[city] = "No Items"
                continue
                
            # Pick the first item
            item = items[0]
            logger.info(f"Selected Item: {item['title']}")
            
            # 1. Refine
            refined_title = gemini_utils.refine_headline(item['title'])
            one_liner = gemini_utils.generate_one_liner(refined_title)
            
            # 2. Search & Verify (The Core Test)
            logger.info(f"Searching Image for: {refined_title}")
            serp_candidates = image_searcher.search_google_images(refined_title)
            final_image_url = None
            
            if serp_candidates:
                for idx, candidate_url in enumerate(serp_candidates):
                    is_good = gemini_utils.verify_image_usability(candidate_url, related_headline=refined_title)
                    if is_good:
                        final_image_url = candidate_url
                        logger.info(f"ACCEPTED Candidate {idx+1}")
                        break
                    else:
                        logger.warning(f"REJECTED Candidate {idx+1}")
            
            # 3. Generate
            img_io = image_generator.create_news_image(
                refined_title, 
                item['source'], 
                "Test Date", 
                final_image_url, 
                summary=one_liner
            )
            
            if img_io:
                size = img_io.getbuffer().nbytes
                status = "Real Image" if size > 60000 else "Gradient Fallback"
                logger.info(f"Result for {city}: {status} ({size} bytes)")
                results[city] = f"{status} ({size} b)"
            else:
                results[city] = "Generation Failed"
                
        except Exception as e:
            logger.error(f"Failed {city}: {e}")
            results[city] = f"Error: {e}"
            
    logger.info("\n=== FINAL REPORT ===")
    for city, res in results.items():
        logger.info(f"{city}: {res}")

def test_template():
    logger.info("=== Testing Image Template (Mock Data) ===")
    
    # Mock Data
    dummy_headline = "This is a Test Headline to Verify the Layout and Font Rendering of the News Bot Template"
    dummy_summary = "Test Source • Just Now • Layout Verification"
    dummy_source = "TestNews"
    dummy_date = "Dec 23, 2025"
    
    # Dummy Image URL (Public placeholder)
    dummy_image_url = "https://dummyimage.com/1080x1350/444444/ffffff&text=Test+Image"
    
    logger.info(f"Headline: {dummy_headline}")
    logger.info(f"Summary: {dummy_summary}")
    logger.info(f"Image: {dummy_image_url}")
    
    # Generate
    try:
        img_io = image_generator.create_news_image(
            dummy_headline, 
            dummy_source, 
            dummy_date, 
            dummy_image_url, 
            summary=dummy_summary
        )
        
        if img_io:
            size = img_io.getbuffer().nbytes
            logger.info(f"Template Test Success! Generated {size} bytes.")
            logger.info("Check workspace/ for the result.")
        else:
            logger.error("Template Test Failed: No image generated.")
            
    except Exception as e:
        logger.error(f"Template Test Error: {e}")

def test_manual_create():
    logger.info("=== Testing Manual Image Gen ===")
    from src import image_generator
    from PIL import Image
    
    # Create valid dummy image
    dummy_img = Image.new('RGB', (800, 600), color=(100, 50, 50))
    dummy_title = "MMMMM WWWWW Wide Characters Stress Test to Verify Absolute Safety Zones With Pixel Measurement"
    dummy_sub = "This headline contains many wide letters (M, W) which often break simple estimation heuristics."
    manual_hex = "#FF0000"
    
    logger.info(f"Generating with Manual Color: {manual_hex}")
    
    img_io = image_generator.create_news_image(
        title=dummy_title,
        source="Manual Test",
        date_str="Now",
        image_url=None,
        summary=dummy_sub,
        manual_image=dummy_img,
        manual_color=manual_hex
    )
    
    if img_io:
        logger.info(f"Success! Generated {img_io.getbuffer().nbytes} bytes.")
        with open("workspace/manual_test_output.png", "wb") as f:
            f.write(img_io.getbuffer())
        logger.info("Saved to workspace/manual_test_output.png")
    else:
        logger.error("Failed to generate manual image.")

def main():
    parser = argparse.ArgumentParser(description="Debug Suite for News Bot")
    parser.add_argument("--step", choices=['fetch', 'db', 'x', 'gemini', 'image', 'multi', 'template', 'create', 'all'], required=True, help="Component to test")
    
    args = parser.parse_args()
    
    try:
        if args.step in ['fetch', 'all']:
            test_fetch()
        if args.step in ['db', 'all']:
            test_db()
        if args.step in ['x', 'all']:
            test_x()
        if args.step in ['gemini', 'all']:
            test_gemini()
        if args.step in ['image', 'all']:
            test_image()
        if args.step in ['multi', 'all']:
            test_multi()
        if args.step in ['template', 'all']:
            test_template()
        if args.step in ['create', 'all']:
            test_manual_create()
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")

if __name__ == "__main__":
    main()
