import httpx
from bs4 import BeautifulSoup


def get_sitemap_urls(domain):
    sitemap_url = domain.rstrip("/") + "/sitemap.xml"
    urls = []

    try:
        r = httpx.get(sitemap_url, timeout=10)

        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "xml")

        for loc in soup.find_all("loc"):
            urls.append(loc.text.strip())

    except:
        return []

    return urls
