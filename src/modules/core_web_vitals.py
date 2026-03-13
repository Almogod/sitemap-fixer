# src/modules/core_web_vitals.py

from bs4 import BeautifulSoup
from urllib.parse import urlparse


LCP_IMAGE_THRESHOLD = 1200  # pixels heuristic
MAX_DOM_ELEMENTS = 1500


def run(context):

    pages = context["pages"]

    issues = []
    suggestions = {}

    for page in pages:

        url = page.get("url")
        html = page.get("html")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        page_suggestions = []

        # --------------------------
        # Detect render blocking CSS
        # --------------------------
        stylesheets = soup.find_all("link", rel="stylesheet")

        if len(stylesheets) > 2:

            issues.append({
                "url": url,
                "issue": "render_blocking_css"
            })

            page_suggestions.append({
                "type": "optimize_css",
                "action": "inline_critical_css_or_defer"
            })

        # --------------------------
        # Detect large images (LCP risk)
        # --------------------------
        images = soup.find_all("img")

        for img in images:

            width = img.get("width")
            height = img.get("height")

            if width and int(width) > LCP_IMAGE_THRESHOLD:

                issues.append({
                    "url": url,
                    "issue": "large_image_lcp_risk",
                    "image": img.get("src")
                })

                page_suggestions.append({
                    "type": "compress_image",
                    "image": img.get("src")
                })

        # --------------------------
        # Missing width/height (CLS)
        # --------------------------
        for img in images:

            if not img.get("width") or not img.get("height"):

                issues.append({
                    "url": url,
                    "issue": "missing_image_dimensions",
                    "image": img.get("src")
                })

                page_suggestions.append({
                    "type": "add_image_dimensions",
                    "image": img.get("src")
                })

        # --------------------------
        # Large DOM size
        # --------------------------
        dom_size = len(soup.find_all())

        if dom_size > MAX_DOM_ELEMENTS:

            issues.append({
                "url": url,
                "issue": "large_dom",
                "size": dom_size
            })

            page_suggestions.append({
                "type": "reduce_dom_size",
                "current_size": dom_size
            })

        # --------------------------
        # JS blocking resources
        # --------------------------
        scripts = soup.find_all("script", src=True)

        for script in scripts:

            if not script.get("async") and not script.get("defer"):

                issues.append({
                    "url": url,
                    "issue": "blocking_js",
                    "script": script.get("src")
                })

                page_suggestions.append({
                    "type": "defer_script",
                    "script": script.get("src")
                })

        if page_suggestions:
            suggestions[url] = page_suggestions

    return {
        "issues": issues,
        "suggestions": suggestions
    }
