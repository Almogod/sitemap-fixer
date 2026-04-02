import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from src.utils.logger import logger

MAX_REDIRECTS_TO_FLAG = 2
REQUEST_TIMEOUT = 10
MAX_CONCURRENCY = 15

def run(context):
    """
    Synchronous entry point for the engine.
    Wraps the async execution of link checks.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If in a thread with a running loop (though rare in background tasks)
            # we might need to use a different approach, but usually asyncio.run is safer for new threads.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(_run_async(context))).result()
        return asyncio.run(_run_async(context))
    except RuntimeError:
        # Fallback for "no event loop" or "loop already running"
        return asyncio.run(_run_async(context))
    except Exception as e:
        logger.error(f"Broken links module critical failure: {e}")
        return {"issues": [], "suggestions": {}, "error": str(e)}

async def _run_async(context):
    pages = context["pages"]
    domain = context.get("domain", "")

    issues = []
    suggestions = {}
    
    # 1. Collect all unique links across all pages
    unique_links = {} # link -> list of (page_url, context_type)
    
    for page in pages:
        url = page.get("url")
        html = page.get("html")
        if not html:
            continue
            
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            
            link = urljoin(url, href)
            
            # Context extraction
            context_type = "generic"
            parent = a.find_parent(["footer", "nav", "header", "aside"])
            if parent:
                context_type = parent.name
            elif any(cls in "".join(a.get("class", [])).lower() for cls in ["cta", "btn", "button"]):
                context_type = "cta"
            
            if link not in unique_links:
                unique_links[link] = []
            unique_links[link].append({"url": url, "context": context_type})

    # 2. Check all unique links in parallel
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT, verify=True) as client:
        tasks = [
            _check_link_async(client, link, semaphore, domain)
            for link in unique_links.keys()
        ]
        results = await asyncio.gather(*tasks)

    # 3. Map results back to issues and suggestions
    enriched_issues = [
        {"type": "broken_link_internal", "severity": "critical", "pages": []},
        {"type": "broken_link_external", "severity": "major", "pages": []},
        {"type": "redirect_chain", "severity": "minor", "pages": []}
    ]

    def get_issue(issue_type):
        for i in enriched_issues:
            if i["type"] == issue_type: return i
        return None

    # 3. Map results back to issues and suggestions
    link_results = dict(zip(unique_links.keys(), results))
    
    for link, res in link_results.items():
        status = res["status"]
        error_type = res.get("error_type")
        redirect_count = res["redirects"]
        is_external = urlparse(link).netloc != domain
        
        # Soft 404 check
        if not is_external and status == 200 and res.get("html"):
            if _is_soft_404(res["html"]):
                status = 404
                error_type = "soft_404"

        # Categorize
        if status >= 400 or status == 0:
            issue_type = "broken_link_external" if is_external else "broken_link_internal"
            issue_obj = get_issue(issue_type)
            for source in unique_links[link]:
                url = source["url"]
                issue_obj["pages"].append(url)
                if url not in suggestions:
                    suggestions[url] = []
                suggestions[url].append({
                    "type": "fix_broken_link",
                    "link": link,
                    "action": f"Remove or replace this {source['context']} link on {url}"
                })
        
        elif redirect_count > MAX_REDIRECTS_TO_FLAG:
            issue_obj = get_issue("redirect_chain")
            for source in unique_links[link]:
                url = source["url"]
                issue_obj["pages"].append(url)
                if url not in suggestions:
                    suggestions[url] = []
                suggestions[url].append({
                    "type": "update_link",
                    "link": link,
                    "action": "Replace with the final destination URL"
                })

    return {
        "issues": enriched_issues,
        "suggestions": suggestions
    }

async def _check_link_async(client, url, semaphore, domain):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    
    async with semaphore:
        try:
            # Try HEAD first
            try:
                response = await client.head(url, headers=headers)
                if response.status_code == 405:
                    response = await client.get(url, headers=headers)
            except (httpx.HTTPStatusError, httpx.RequestError):
                response = await client.get(url, headers=headers)

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
    if not html: return False
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not body: return False
    text = body.get_text().lower()
    if len(text) < 1500:
        indicators = ["404", "not found", "page not found", "doesn't exist", "error 404"]
        if any(ind in text for ind in indicators):
            return True
    return False
