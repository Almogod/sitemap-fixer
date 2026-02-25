from bs4 import BeautifulSoup

def extract_metadata(page):
    soup = BeautifulSoup(page["html"], "lxml")

    canonical_tag = soup.find("link", rel="canonical")
    robots_tag = soup.find("meta", attrs={"name": "robots"})

    canonical = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else page["url"]

    noindex = False
    if robots_tag and robots_tag.get("content"):
        noindex = "noindex" in robots_tag["content"].lower()

    return {
        "url": page["url"],
        "status": page["status"],
        "canonical": canonical,
        "noindex": noindex
    }
