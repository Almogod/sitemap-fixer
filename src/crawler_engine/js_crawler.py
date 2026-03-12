import asyncio
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


class JSCrawler:
    """
    Headless browser crawler for JS-rendered websites.
    Used when normal HTTP crawler cannot discover links.
    """

    def __init__(self, start_url, limit=50, concurrency=3):
        self.start_url = start_url
        self.limit = limit
        self.concurrency = concurrency

        self.visited = set()
        self.to_visit = {start_url}
        self.results = []

        self.domain = urlparse(start_url).netloc

    async def crawl(self):

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            semaphore = asyncio.Semaphore(self.concurrency)

            async def worker():

                page = await browser.new_page()

                while self.to_visit and len(self.results) < self.limit:

                    try:
                        url = self.to_visit.pop()
                    except KeyError:
                        return

                    if url in self.visited:
                        continue

                    async with semaphore:

                        try:
                            await page.goto(
                                url,
                                timeout=15000,
                                wait_until="domcontentloaded"
                            )

                            html = await page.content()

                            self.visited.add(url)

                            page_data = {
                                "url": url,
                                "status": 200,
                                "html": html
                            }

                            self.results.append(page_data)

                            links = self.extract_links(html, url)

                            for link in links:
                                if link not in self.visited:
                                    self.to_visit.add(link)

                        except Exception:
                            continue

                await page.close()

            workers = [worker() for _ in range(self.concurrency)]

            await asyncio.gather(*workers)

            await browser.close()

        return self.results

    def extract_links(self, html, base_url):

        soup = BeautifulSoup(html, "lxml")

        links = []

        for tag in soup.find_all("a", href=True):

            href = tag["href"]

            absolute = urljoin(base_url, href)

            parsed = urlparse(absolute)

            if parsed.netloc == self.domain:
                links.append(absolute)

        return links


def crawl_js_sync(start_url, limit=50):
    """
    Synchronous wrapper for FastAPI usage.
    """

    crawler = JSCrawler(start_url, limit)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(crawler.crawl())
    finally:
        loop.close()
