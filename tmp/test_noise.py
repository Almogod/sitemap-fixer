
import sys
import os
from collections import Counter

# Add src to path
sys.path.append(os.getcwd())

from src.content.engine import is_noise, _extract_bulk_keywords

def test_noise_filter():
    noise_words = ["xon", "bqh", "wtj", "vuf", "wvg", "atp", "bou", "kjc", "yoe", "jcn", "hei", "snn", "ncr"]
    valid_words = ["engineering", "solutions", "software", "development", "industrial"]
    
    print("Testing is_noise function...")
    for w in noise_words:
        assert is_noise(w) == True, f"Failed to detect noise: {w}"
    
    for w in valid_words:
        assert is_noise(w) == False, f"Mistakenly marked valid word as noise: {w}"
    
    print("SUCCESS: Noise filter is working correctly.")

    print("\nTesting _extract_bulk_keywords with noise...")
    mock_pages = [
        {"title": "Industrial Engineering", "html": "<html><body><div class='vuf bqh'>Engineering focus on xon and wtj</div></body></html>"}
    ]
    keywords = _extract_bulk_keywords(mock_pages)
    print(f"Extracted Keywords: {list(keywords.keys())}")
    
    for nw in noise_words:
        if nw in keywords:
            print(f"FAILURE: Noise word '{nw}' found in keywords!")
            return
            
    print("SUCCESS: Keywords are clean of noise.")

if __name__ == "__main__":
    test_noise_filter()
