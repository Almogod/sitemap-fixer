import asyncio
import httpx
import time
import base64
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from .fetcher import fetch
from src.config import config
from src.utils.logger import logger


async def run_workers(frontier, parser, graph, start_url=None, limit=200, concurrency=10, delay=1.0, check_robots=True, extra_headers=None, broken_links_only=False, max_depth=10, crawl_assets=False, custom_selectors=None):
    results = []
    rp = None
    from .frontier import ensure_scheme, is_internal_domain
    comp_url = ensure_scheme(start_url)
    
    if check_robots:
        try:
            first_url = None
            if hasattr(frontier, 'peek'): first_url = frontier.peek()
            if not first_url and hasattr(frontier, 'visited') and frontier.visited:
                first_url = next(iter(frontier.visited))
            if first_url:
                parsed = urlparse(first_url)
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(robots_url)
                    if resp.status_code == 200:
                        rp = RobotFileParser()
                        rp.parse(resp.text.splitlines())
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt: {e}")

    mounts = {}
    if config.CRAWLER_PROXY:
        mounts = {"all://": httpx.AsyncHTTPTransport(proxy=config.CRAWLER_PROXY)}

    headers = {}
    if config.CRAWLER_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {config.CRAWLER_BEARER_TOKEN}"
    elif config.CRAWLER_BASIC_AUTH:
        encoded = base64.b64encode(config.CRAWLER_BASIC_AUTH.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    if extra_headers: headers.update(extra_headers)

    async with httpx.AsyncClient(timeout=config.CRAWL_TIMEOUT, headers=headers, mounts=mounts, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(concurrency)
        cv = asyncio.Condition()
        active_workers = 0


        async def worker():
            nonlocal active_workers
            while True:
                item = None
                async with cv:
                    while not frontier.size() and len(results) < limit:
                        if active_workers == 0:
                            cv.notify_all()
                            return
                        await cv.wait()
                    
                    if len(results) >= limit:
                        cv.notify_all()
                        return
                    
                    item = frontier.get()
                    if item:
                        active_workers += 1

                if not item: continue

                url = item["url"]
                depth = item["depth"]

                try:
                    # Robots check
                    if rp and not rp.can_fetch("*", url):
                        logger.warning(f"Skipping {url} (Blocked by robots.txt)")
                        continue

                    async with semaphore:
                        if delay > 0: await asyncio.sleep(delay)
                        page = await fetch(client, url)

                    if not page: continue
                    
                    status = page.get("status")
                    parsed_u = urlparse(url)
                    # FIX: Use shared 'www-agnostic' check here to prevent skipping metadata on internal redirects
                    is_external = frontier.base_domain and parsed_u.netloc and not is_internal_domain(parsed_u.netloc, frontier.base_domain)

                    # Metadata init
                    page.update({"meta": {}, "headings": {}, "images": [], "videos": [], "hreflangs": [], "custom": {}, "canonical": ""})

                    if broken_links_only:
                        if (url == comp_url) or (status and status not in [200, 304]):
                            results.append(page)
                    else:
                        results.append(page)
                        logger.info(f"Fetched {url} ({status}). Progress: {len(results)}/{limit}")

                    # FIX: Metadata collection and link extraction must work for internal pages
                    if status == 200 and page.get("html") and not is_external and depth < max_depth:
                        extracted = parser(page["html"], page["url"], custom_selectors=custom_selectors)
                        page.update({
                            "hreflangs": extracted.get("hreflangs", []), "images": extracted.get("images", []),
                            "videos": extracted.get("videos", []), "canonical": extracted.get("canonical", ""),
                            "meta": extracted.get("meta", {}), "headings": extracted.get("headings", {}),
                            "custom": extracted.get("custom", {})
                        })

                        for link in extracted.get("links", []):
                            graph.add_edge(page["url"], link)
                            parsed_link = urlparse(link)
                            # FIX: Use shared 'www-agnostic' check for outgoing links too
                            is_target_ext = frontier.base_domain and parsed_link.netloc and not is_internal_domain(parsed_link.netloc, frontier.base_domain)
                            target_depth = max_depth + 1 if is_target_ext else depth + 1
                            priority = 1 if is_target_ext else 10
                            frontier.add(link, depth=target_depth, force_add=is_target_ext, priority=priority)
                            
                        if crawl_assets:
                            for asset in extracted.get("assets", []):
                                graph.add_edge(page["url"], asset)
                                frontier.add(asset, depth=max_depth + 1, force_add=True, priority=5)
                except Exception as e:
                    logger.error(f"Worker Error: {e}")
                finally:
                    async with cv:
                        active_workers -= 1
                        cv.notify_all()

        workers = [worker() for _ in range(concurrency)]
        await asyncio.gather(*workers)

    return results
