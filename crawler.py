import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl(start_url, limit=200):
    visited = set()
    to_visit = set([start_url])
    results = []

    with httpx.Client(timeout=10, follow_redirects=True) as client:
        while to_visit and len(visited) < limit:
            url = to_visit.pop()

            if url in visited:
                continue

            try:
                r = client.get(url)
                visited.add(url)

                results.append({
                    "url": url,
                    "status": r.status_code,
                    "html": r.text
                })

                if "text/html" in r.headers.get("content-type", ""):
                    soup = BeautifulSoup(r.text, "lxml")

                    for link in soup.find_all("a", href=True):
                        new_url = urljoin(url, link["href"])

                        if urlparse(new_url).netloc == urlparse(start_url).netloc:
                            to_visit.add(new_url)

            except:
                continue

    return results
