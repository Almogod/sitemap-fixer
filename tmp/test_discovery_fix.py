import sys
import os
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.crawler_engine.frontier import SQLiteURLFrontier
from src.content.engine import analyze_site_content, generate_markdown_site_profile

def test_www_normalization():
    print("Testing Frontier www-normalization...")
    f = SQLiteURLFrontier(base_domain="qcecuring.com")
    
    # 1. Add www version
    f.add("https://www.qcecuring.com/services")
    # 2. Add non-www version
    f.add("https://qcecuring.com/about")
    # 3. Add external domain
    f.add("https://google.com")
    
    # Verify both are in the queue (or visited)
    conn = f._get_conn()
    res = conn.execute("SELECT url FROM visited").fetchall()
    urls = [r[0] for r in res]
    print(f"Visited URLs: {urls}")
    
    assert "https://www.qcecuring.com/services" in urls
    assert "https://qcecuring.com/about" in urls
    assert "https://google.com" not in urls
    print("✓ WWW-Normalization Passed")

def test_data_guard():
    print("\nTesting Discovery Data Guard...")
    # Empty pages - should return crawler_no_data
    res = analyze_site_content([], "example.com")
    assert res["discovery_method"] == "crawler_no_data"
    
    md = generate_markdown_site_profile(res)
    print(f"Markdown Audit (Empty Case):\n{md[:100]}...")
    assert "[!WARNING]" in md
    assert "No Data Found" in md
    print("✓ Data Guard Passed")

if __name__ == "__main__":
    try:
        test_www_normalization()
        test_data_guard()
        print("\nAll Discovery Fix Tests Passed!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
