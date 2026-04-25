# src/modules/keyword_gap.py

from bs4 import BeautifulSoup
from collections import Counter
import re
import httpx

from src.content.stopwords import STOPWORDS
from src.utils.security import is_safe_url


def run(context):

    pages = context["pages"]
    competitors = context.get("competitors", [])

    site_keywords = extract_site_keywords(pages)

    competitor_keywords = {}

    for competitor in competitors:

        try:
            competitor_pages = fetch_competitor_pages(competitor)
            competitor_keywords[competitor] = extract_site_keywords(competitor_pages)
        except Exception:
            competitor_keywords[competitor] = []

    keyword_gap = {}

    for competitor, keywords in competitor_keywords.items():

        gap = [k for k in keywords if k not in site_keywords]

        keyword_gap[competitor] = gap[:20]

    return {
        "site_keywords": site_keywords[:50],
        "competitor_keywords": competitor_keywords,
        "keyword_gap": keyword_gap
    }


def extract_site_keywords(pages):
    """Extract keywords from pages using unigrams and bigrams."""
    words = []
    bigrams = []

    for page in pages:

        html = page.get("html")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        # Extract and weight headings
        heading_text = ""
        for tag in soup.find_all(["h1", "h2", "h3"]):
            h = tag.get_text(strip=True)
            if h:
                heading_text += f" {h} {h} {h}"  # 3x weight

        # Extract title
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""

        # Extract body
        text = soup.get_text(" ")
        
        # Combined text with title/heading boosting
        combined = f"{title_text} {title_text} {title_text} {heading_text} {text}"

        tokens = tokenize(combined)
        words.extend(tokens)
        
        # Extract bigrams
        for i in range(len(tokens) - 1):
            bigrams.append(f"{tokens[i]} {tokens[i+1]}")

    # Combine unigrams and frequent bigrams
    unigram_counter = Counter(words)
    bigram_counter = Counter(bigrams)
    
    # Merge: bigrams with freq >= 2 first, then unigrams
    result = []
    seen = set()
    
    for bg, cnt in bigram_counter.most_common(50):
        if cnt >= 2 and bg not in seen:
            result.append(bg)
            seen.add(bg)
    
    for w, _ in unigram_counter.most_common(200):
        if w not in seen:
            result.append(w)
            seen.add(w)

    return result[:200]


def tokenize(text):

    text = text.lower()

    # Allow alphanumeric tokens (catches api, h2o, css3, etc.)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    tokens = text.split()

    # Keep tokens with 3+ chars that aren't stopwords, PLUS known technical abbreviations
    from src.content.phrase_extractor import _is_technical_abbreviation
    tokens = [
        t for t in tokens 
        if (len(t) >= 3 and t not in STOPWORDS) or _is_technical_abbreviation(t)
    ]

    return tokens


def fetch_competitor_pages(domain):

    urls = [
        domain,
        f"{domain}/blog",
        f"{domain}/articles"
    ]

    pages = []

    for url in urls:
        if not is_safe_url(url):
            continue

        try:

            r = httpx.get(url, timeout=10)

            pages.append({
                "url": url,
                "html": r.text,
                "status": r.status_code
            })

        except Exception:
            continue

    return pages
