from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

# Common locale patterns in URLs (e.g. /en/, /fr/, /es-mx/)
LOCALE_PATTERN = re.compile(r"/([a-z]{2}(?:-[a-zA-Z]{2,4})?)/", re.IGNORECASE)
LANG_IN_DOMAIN = re.compile(r"^(en|fr|de|es|it|pt|nl|ru|zh|ja|ko|ar)\.", re.IGNORECASE)

# ISO 639-1 language codes (sample for validation)
VALID_LANGS = {"en", "fr", "de", "es", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "he", "hi", "tr", "vi", "pl"}

def run(context):
    pages = context["pages"]
    domain = context.get("domain", "")

    issues = []
    suggestions = {}

    # 1. Map all URLs to their hreflang declarations for reciprocal checks
    url_to_hreflangs = {}
    for page in pages:
        url = page.get("url")
        html = page.get("html")
        if not html:
            continue
        
        soup = BeautifulSoup(html, "lxml")
        hreflangs = []
        for link in soup.find_all("link", rel="alternate", hreflang=True):
            hreflangs.append({
                "hreflang": link["hreflang"].lower(),
                "href": link["href"].strip()
            })
        url_to_hreflangs[url] = hreflangs

    # 2. Detect locales to find pages missing tags entirely
    locale_map = {}
    for page in pages:
        url = page.get("url")
        locale = _detect_locale(url)
        if locale:
            locale_map.setdefault(locale, []).append(url)

    # 3. Validation Loop
    for page in pages:
        url = page.get("url")
        html = page.get("html")
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        page_issues = []
        hreflangs = url_to_hreflangs.get(url, [])

        # Issue: Missing Hreflang entirely on a multi-locale site
        if not hreflangs and len(locale_map) >= 2:
            page_issues.append({
                "issue": "missing_hreflang_tags",
                "detected_locales": list(locale_map.keys())
            })

        # Issue: Reciprocal Check
        for h in hreflangs:
            target_url = h["href"]
            target_hreflangs = url_to_hreflangs.get(target_url, [])
            
            # If target page was crawled, check if it links back
            if target_url in url_to_hreflangs:
                reciprocal = any(th["href"] == url for th in target_hreflangs)
                if not reciprocal:
                    page_issues.append({
                        "issue": "non_reciprocal_hreflang",
                        "target_url": target_url,
                        "hreflang": h["hreflang"]
                    })

        # Issue: Canonical Conflict
        canonical = soup.find("link", rel="canonical")
        if canonical:
            can_url = canonical["href"].strip()
            # If page says it's the 'en' version of itself, but canonical points elsewhere
            self_decl = [h for h in hreflangs if h["href"] == url]
            if self_decl and can_url != url:
                page_issues.append({
                    "issue": "hreflang_canonical_conflict",
                    "canonical_url": can_url
                })

        # Issue: Language Code Validation
        for h in hreflangs:
            lang_code = h["hreflang"].split("-")[0]
            if lang_code not in VALID_LANGS and lang_code != "x-default":
                page_issues.append({
                    "issue": "invalid_language_code",
                    "code": h["hreflang"]
                })

        # Issue: Missing x-default
        if hreflangs and not any(h["hreflang"] == "x-default" for h in hreflangs):
            page_issues.append({
                "issue": "missing_x_default"
            })

        if page_issues:
            for pi in page_issues:
                issues.append({"url": url, **pi})
            
            # Suggestion: Replace all tags with a consistent set
            if len(locale_map) >= 2:
                base_set = []
                for loc, urls in locale_map.items():
                    base_set.append(f'<link rel="alternate" hreflang="{loc}" href="{urls[0]}">')
                # Add x-default (usually English or first one)
                default_url = locale_map.get("en", list(locale_map.values())[0])[0]
                base_set.append(f'<link rel="alternate" hreflang="x-default" href="{default_url}">')
                
                suggestions[url] = [{
                    "type": "hreflang_fix",
                    "action": "replace_hreflang_tags",
                    "tags": base_set
                }]

    return {
        "issues": issues,
        "suggestions": suggestions
    }

def _detect_locale(url):
    """Extract locale code from URL path or subdomain."""
    parsed = urlparse(url)
    subdomain_match = LANG_IN_DOMAIN.match(parsed.netloc)
    if subdomain_match:
        return subdomain_match.group(1).lower()
    path_match = LOCALE_PATTERN.search(parsed.path)
    if path_match:
        return path_match.group(1).lower()
    return None
