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
    # SCORE CALCULATION
    # ------------------------
    deductions = {
        "duplicates": 5,
        "non_200": 10,
        "has_query_params": 5,
        "not_https": 10,
        "deep_pages": 3,
        "excluded_from_sitemap": 2
    }

    for issue, urls in report["issues"].items():
        penalty = deductions.get(issue, 1) * len(urls)
        report["score"] -= penalty

    # Clamp score
    report["score"] = max(0, report["score"])

    # ------------------------
    # FIX SUGGESTIONS
    # ------------------------
    if report["issues"]["duplicates"]:
        report["suggestions"].append("Remove duplicate URLs and ensure each page has a unique canonical URL.")

    if report["issues"]["non_200"]:
        report["suggestions"].append("Fix broken pages (404/500) or remove them from sitemap.")

    if report["issues"]["has_query_params"]:
        report["suggestions"].append("Remove tracking/query parameters (e.g., ?utm=) from URLs in sitemap.")

    if report["issues"]["not_https"]:
        report["suggestions"].append("Ensure all URLs use HTTPS instead of HTTP.")

    if report["issues"]["deep_pages"]:
        report["suggestions"].append("Reduce URL depth. Keep important pages within 2–3 clicks from homepage.")

    if report["issues"]["excluded_from_sitemap"]:
        report["suggestions"].append("Ensure all important pages are included in the sitemap.")

    return report
