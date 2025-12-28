import sys
import os
sys.path.append(os.getcwd())

from src.components.colors import get_dominant_color, force_light_color, is_light
from PIL import Image
import logging

# Setup basic logger
logging.basicConfig(level=logging.INFO)

def test_colors():
    print("=== Testing Color Logic ===")
    
    # 1. Test Black Image
    print("\n1. Testing Black Image (Should lighten to Grey/White)")
    black_img = Image.new('RGB', (100, 100), (0, 0, 0))
    dom = get_dominant_color(black_img, (0, 0, 128)) # Default Navy
    print(f"Input: Black (0,0,0). Result: {dom}")
    print(f"Is Light? {is_light(dom)}")
    
    # 2. Test Dark Blue Image (Should lighten to Pastel Blue)
    print("\n2. Testing Dark Blue (0, 0, 100)")
    blue_img = Image.new('RGB', (100, 100), (0, 0, 100))
    dom = get_dominant_color(blue_img, (0, 0, 0))
    print(f"Input: Dark Blue (0,0,100). Result: {dom}")
    print(f"Is Light? {is_light(dom)}")
    
    # 3. Test Function directly
    res = force_light_color((0, 0, 0))
    print(f"\n3. force_light_color((0,0,0)): {res}")

if __name__ == "__main__":
    test_colors()
