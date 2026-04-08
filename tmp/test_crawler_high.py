import asyncio
import os
from src.crawler_engine.crawler import crawl

async def test_high_limit_crawl():
    # We'll use a known stable site with many links
    test_url = "https://www.wikipedia.org" 
    limit = 100 # Not 700 but enough to test SQLite if I lower the threshold for testing
    
    # Force SQLite for testing
    print(f"Starting high-limit (SQLite) crawl for {test_url}...")
    try:
        pages, graph = crawl(test_url, limit=limit, backend="sqlite")
        print(f"Crawl finished. Found {len(pages)} pages.")
        if len(pages) > 1:
            print("SUCCESS: Found multiple pages with SQLite frontier.")
        else:
            print("FAILURE: Only found 1 page.")
    except Exception as e:
        print(f"Crawl failed with error: {e}")

if __name__ == "__main__":
    import threading
    # Run in a thread to ensure we can test the 'already running loop' fallback
    t = threading.Thread(target=lambda: asyncio.run(test_high_limit_crawl()))
    t.start()
    t.join()
