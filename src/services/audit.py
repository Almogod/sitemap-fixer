from collections import defaultdict
from urllib.parse import urlparse


def generate_audit_report(pages, clean_urls):
    report = {
        "total_pages_crawled": len(pages),
        "total_clean_urls": len(clean_urls),
        "issues": defaultdict(list),
        "score": 100,
        "suggestions": []
    }

    seen = set()

    for p in pages:
        url = p.get("url")
        status = p.get("status", 0)

        if not url:
            continue

        # Duplicate URLs
        if url in seen:
            report["issues"]["duplicates"].append(url)
        else:
            seen.add(url)

        # Non-200 pages
        if status != 200:
            report["issues"]["non_200"].append(url)

        # Query parameters
        if "?" in url:
            report["issues"]["has_query_params"].append(url)

        # Non-HTTPS
        if url.startswith("http://"):
            report["issues"]["not_https"].append(url)

        # Deep paths
        path_depth = len(urlparse(url).path.strip("/").split("/"))
        if path_depth > 4:
            report["issues"]["deep_pages"].append(url)

    # Excluded from sitemap
    clean_set = set(clean_urls)
    for p in pages:
        url = p.get("url")
        if url and url not in clean_set:
            report["issues"]["excluded_from_sitemap"].append(url)

    # ------------------------
    # SCORE CALCULATION (PROPORTIONAL)
    # ------------------------
    # Base score is 100
    # Deductions are calculated as a percentage of pages crawled (max penalty per category)
    max_deductions = {
        "duplicates": 20,              # up to 20 pts off for duplicates
        "non_200": 30,                 # up to 30 pts off for broken pages
        "has_query_params": 10,        # up to 10 pts off for query params
        "not_https": 30,               # up to 30 pts off for non-https
        "deep_pages": 15,              # up to 15 pts off for deep pages
        "excluded_from_sitemap": 10    # up to 10 pts off for omitted pages
    }

    total = len(pages) if len(pages) > 0 else 1

    for issue, urls in report["issues"].items():
        if not urls:
            continue
        
        # Calculate what percentage of the total pages have this issue
        issue_ratio = len(urls) / total
        
        # Scale the maximum penalty for this category by the issue ratio
        max_penalty = max_deductions.get(issue, 5)
        
        # We apply a slight curve to punish even small amounts of critical errors (like non-200) more heavily
        # but cap it at max_penalty. e.g. min(issue_ratio * 2.0, 1.0) * max_penalty
        severity_multiplier = 2.0 if issue in ["non_200", "not_https"] else 1.2
        
        applied_ratio = min(issue_ratio * severity_multiplier, 1.0)
        penalty = int(applied_ratio * max_penalty)
        
        report["score"] -= penalty

    # Clamp score between 0 and 100
    report["score"] = max(0, min(100, report["score"]))

    # ------------------------
    # FIX SUGGESTIONS
    # ------------------------
    if report["issues"].get("duplicates"):
        report["suggestions"].append("Remove duplicate URLs and ensure each page has a unique canonical URL.")

    if report["issues"].get("non_200"):
        report["suggestions"].append("Fix broken pages (404/500) or remove them from sitemap.")

    if report["issues"].get("has_query_params"):
        report["suggestions"].append("Remove tracking/query parameters (e.g., ?utm=) from URLs in sitemap.")

    if report["issues"].get("not_https"):
        report["suggestions"].append("Ensure all URLs use HTTPS instead of HTTP.")

    if report["issues"].get("deep_pages"):
        report["suggestions"].append("Reduce URL depth. Keep important pages within 2–3 clicks from homepage.")

    if report["issues"].get("excluded_from_sitemap"):
        report["suggestions"].append("Ensure all important pages are included in the sitemap.")

    return report
