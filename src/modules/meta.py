# src/modules/meta.py

from bs4 import BeautifulSoup
from collections import defaultdict


def analyze_meta(pages):
    issues = defaultdict(list)

    for p in pages:
        html = p.get("html", "")
        url = p.get("url")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        title = soup.find("title")
        desc = soup.find("meta", attrs={"name": "description"})
        h1 = soup.find("h1")

        # Missing title
        if not title or not title.text.strip():
            issues["missing_title"].append(url)

        # Missing description
        if not desc or not desc.get("content", "").strip():
            issues["missing_description"].append(url)

        # Multiple H1
        h1_tags = soup.find_all("h1")
        if len(h1_tags) > 1:
            issues["multiple_h1"].append(url)

        # Missing H1
        if not h1:
            issues["missing_h1"].append(url)

    return issues


def generate_meta_tags(pages):
    fixes = {}

    for p in pages:
        html = p.get("html", "")
        url = p.get("url")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        title = soup.find("title")
        h1 = soup.find("h1")

        # Generate title
        if not title or not title.text.strip():
            if h1:
                new_title = h1.text.strip()
            else:
                new_title = generate_title_from_url(url)
        else:
            new_title = title.text.strip()

        # Generate description
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if not desc_tag or not desc_tag.get("content"):
            desc = generate_description(soup)
        else:
            desc = desc_tag.get("content")

        fixes[url] = {
            "title": new_title[:60],
            "description": desc[:155]
        }

    return fixes


def generate_title_from_url(url):
    slug = url.rstrip("/").split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ")
    return slug.title()


def generate_description(soup):
    p = soup.find("p")

    if p and p.text:
        text = p.text.strip()
        return text[:155]

    return "Learn more about this page."
