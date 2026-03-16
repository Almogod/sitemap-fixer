import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from src.utils.logger import logger

MAX_REDIRECTS_TO_FLAG = 2
REQUEST_TIMEOUT = 10

def run(context):
    pages = context["pages"]
    domain = context.get("domain", "")

    issues = []
    suggestions = {}
    checked_cache = {}  # avoid re-checking the same URL

    for page in pages:
        url = page.get("url")
        html = page.get("html")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        page_suggestions = []

        # Find all links and their context
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            
            link = urljoin(url, href)
            is_external = urlparse(link).netloc != domain
            
            # Context extraction
            context_type = "generic"
            parent = a.find_parent(["footer", "nav", "header", "aside"])
            if parent:
                context_type = parent.name
            elif any(cls in "".join(a.get("class", [])).lower() for cls in ["cta", "btn", "button"]):
                context_type = "cta"

            if link in checked_cache:
                result = checked_cache[link]
            else:
                result = _check_link(link)
                checked_cache[link] = result

            status = result["status"]
            error_type = result.get("error_type")
            redirect_count = result["redirects"]
            
            # Soft 404 check (only for internal links)
            if not is_external and status == 200 and result.get("html"):
                if _is_soft_404(result["html"]):
                    status = 404
                    error_type = "soft_404"

            # ─────────────────────────────────────
            # Broken link or categorization
            # ─────────────────────────────────────
            if status >= 400 or status == 0:
                issues.append({
                    "url": url,
                    "issue": "broken_link",
                    "link": link,
                    "is_external": is_external,
                    "context": context_type,
                    "status": status,
                    "error_category": error_type or ("http_error" if status >= 400 else "unknown")
                })
                page_suggestions.append({
                    "type": "fix_broken_link",
                    "link": link,
                    "action": f"Remove or replace this {context_type} link on {url}"
                })

            # ─────────────────────────────────────
            # Redirect chain
            # ─────────────────────────────────────
            elif redirect_count > MAX_REDIRECTS_TO_FLAG:
                issues.append({
                    "url": url,
                    "issue": "redirect_chain",
                    "link": link,
                    "is_external": is_external,
                    "redirects": redirect_count
                })
                page_suggestions.append({
                    "type": "update_link",
                    "link": link,
                    "action": "Replace with the final destination URL"
                })

        if page_suggestions:
            suggestions[url] = page_suggestions

    return {
        "issues": issues,
        "suggestions": suggestions
    }


def _check_link(url):
    """
    Returns a result dict: {status, redirects, [html], [error_type]}.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    try:
        with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers, verify=True) as client:
            # Try HEAD first
            try:
                response = client.head(url)
                if response.status_code == 405: # Method not allowed
                    response = client.get(url)
            except (httpx.HTTPStatusError, httpx.RequestError):
                response = client.get(url)

            return {
                "status": response.status_code,
                "redirects": len(response.history),
                "html": response.text if response.status_code == 200 else None
            }
    except httpx.ConnectTimeout:
        return {"status": 0, "redirects": 0, "error_type": "timeout"}
    except (httpx.ConnectError, httpx.NetworkError):
        return {"status": 0, "redirects": 0, "error_type": "dns_or_connection_failure"}
    except httpx.ProtocolError:
        return {"status": 0, "redirects": 0, "error_type": "protocol_error"}
    except Exception as e:
        err_str = str(e).lower()
        if "ssl" in err_str or "cert" in err_str:
            return {"status": 0, "redirects": 0, "error_type": "ssl_error"}
        return {"status": 0, "redirects": 0, "error_type": "unknown"}


def _is_soft_404(html):
    """Detects 'Soft 404' by looking for common error strings in page text."""
    if not html:
        return False
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body:
        return False
    
    text = body.get_text().lower()
    # If the page is very small and contains error words
    if len(text) < 1500:
        indicators = ["404", "not found", "page not found", "doesn't exist", "error 404"]
        if any(ind in text for ind in indicators):
            return True
    return False
