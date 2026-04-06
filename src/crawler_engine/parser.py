from bs4 import BeautifulSoup
from lxml import html as lxml_html
from urllib.parse import urljoin, urlparse
import re
from src.utils.logger import logger


def extract_links(html, base_url, custom_selectors=None):
    soup = BeautifulSoup(html, "lxml")
    dom = lxml_html.fromstring(html) if html else None
    
    links = []
    assets = []
    hreflangs = []
    images = []
    videos = []
    
    # Canonical
    canonical = ""
    can_tag = soup.find("link", rel="canonical", href=True)
    if can_tag:
        canonical = urljoin(base_url, can_tag["href"])

    # 1. Links
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"])
        if urlparse(url).scheme.startswith("http"):
            links.append(url)

    # 2. Assets (CSS/JS)
    for link in soup.find_all("link", rel="stylesheet", href=True):
        url = urljoin(base_url, link["href"])
        if urlparse(url).scheme.startswith("http"):
            assets.append(url)
            
    for script in soup.find_all("script", src=True):
        url = urljoin(base_url, script["src"])
        if urlparse(url).scheme.startswith("http"):
            assets.append(url)
            
    # 3. Hreflang
    for link in soup.find_all("link", rel="alternate", hreflang=True, href=True):
        hreflangs.append({
            "rel": "alternate",
            "hreflang": link["hreflang"],
            "href": urljoin(base_url, link["href"])
        })
        
    # 4. Images
    for img in soup.find_all("img", src=True):
        img_url = urljoin(base_url, img["src"])
        if urlparse(img_url).scheme.startswith("http"):
            assets.append(img_url)
        images.append({
            "loc": img_url,
            "title": img.get("alt", ""),
            "caption": img.get("title", "")
        })
        
    # 6. SEO Meta Audit (with OpenGraph Fallbacks)
    meta_title = soup.title.get_text().strip() if soup.title else ""
    
    # Try og:title if title is empty
    if not meta_title:
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
        if og_title:
            meta_title = og_title.get("content", "").strip()
    
    # Final title fallback: First H1
    if not meta_title:
        h1 = soup.find("h1")
        if h1:
            meta_title = h1.get_text().strip()

    meta_desc = ""
    # Case-insensitive search for description
    desc_tag = soup.find("meta", attrs={"name": re.compile(r'^description$', re.I)}) or \
               soup.find("meta", property="og:description")
    if desc_tag:
        meta_desc = desc_tag.get("content", "").strip()
        
    meta_robots = ""
    robots_tag = soup.find("meta", attrs={"name": re.compile(r'^robots$', re.I)})
    if robots_tag:
        meta_robots = robots_tag.get("content", "").strip()
        
    # 7. Heading Hierarchy
    headings = {
        "h1": [h.get_text().strip() for h in soup.find_all("h1")],
        "h2": [h.get_text().strip() for h in soup.find_all("h2")],
        "h3": [h.get_text().strip() for h in soup.find_all("h3")],
        "h4": [h.get_text().strip() for h in soup.find_all("h4")],
    }
    
    # 8. Custom Selectors (CSS/XPath)
    custom_data = {}
    if custom_selectors:
        for field, selector in custom_selectors.items():
            try:
                if selector.startswith(("/", "(")): # Simple XPath detect
                    if dom is not None:
                        res = dom.xpath(selector)
                        custom_data[field] = [str(r.text) if hasattr(r, "text") else str(r) for r in res]
                else: # CSS Selector
                    res = soup.select(selector)
                    custom_data[field] = [r.get_text().strip() for r in res]
            except Exception as e:
                custom_data[field] = f"Error: {str(e)}"

    # 9. Word Count (Approximate)
    text = soup.get_text()
    word_count = len(text.split())
    
    return {
        "links": list(set(links)),
        "assets": list(set(assets)),
        "canonical": canonical,
        "hreflangs": hreflangs,
        "images": images,
        "videos": videos,
        "meta": {
            "title": meta_title,
            "description": meta_desc,
            "robots": meta_robots,
            "word_count": word_count
        },
        "headings": headings,
        "custom": custom_data
    }
