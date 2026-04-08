import asyncio
from src.crawler_engine.crawler import crawl

def test_isolated_crawl():
    # We'll use a known stable site for a very shallow crawl
    test_url = "https://example.com"
    print(f"Starting isolated crawl for {test_url}...")
    try:
        pages, graph = crawl(test_url, limit=5, max_depth=1)
        print(f"Crawl finished. Found {len(pages)} pages.")
        for p in pages:
            print(f"- {p['url']} ({p['status']})")
    except Exception as e:
        print(f"Crawl failed with error: {e}")

if __name__ == "__main__":
    test_isolated_crawl()
