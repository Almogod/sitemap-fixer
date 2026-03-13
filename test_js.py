from src.crawler_engine.js_crawler import crawl_js_sync

pages = crawl_js_sync("https://books.toscrape.com", 5)

print("Pages:", len(pages))
