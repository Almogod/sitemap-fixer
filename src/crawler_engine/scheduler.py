import asyncio
import httpx
import time
import base64
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from .fetcher import fetch
from src.config import config
from src.utils.logger import logger


async def run_workers(frontier, parser, graph, limit=200, concurrency=10, delay=1.0, check_robots=True, extra_headers=None, broken_links_only=False, max_depth=10, crawl_assets=False, custom_selectors=None):
    results = []
    broken_links = []
    rp = None
    
    # 1. Asynchronous robots.txt handling
    if check_robots:
        try:
            # We try to get the base domain from the first available URL
            first_url = None
            if hasattr(frontier, 'peek'):
                first_url = frontier.peek()
            
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
                        logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt: {e}")

    # 2. Client configuration (Proxy & Auth)
    mounts = {}
    if config.CRAWLER_PROXY:
        mounts = {"all://": httpx.AsyncHTTPTransport(proxy=config.CRAWLER_PROXY)}

    headers = {}
    if config.CRAWLER_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {config.CRAWLER_BEARER_TOKEN}"
    elif config.CRAWLER_BASIC_AUTH:
        encoded = base64.b64encode(config.CRAWLER_BASIC_AUTH.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    
    if extra_headers:
        headers.update(extra_headers)

    async with httpx.AsyncClient(
        timeout=config.CRAWL_TIMEOUT, 
        headers=headers,
        mounts=mounts,
        follow_redirects=True
    ) as client:

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

                if not item:
                    continue

                url = item["url"]
                depth = item["depth"]

                try:
                    # Robots.txt check
                    if rp and not rp.can_fetch("*", url):
                        logger.debug(f"Skipping {url} due to robots.txt")
                        async with cv:
                            active_workers -= 1
                            cv.notify_all()
                        continue

                    async with semaphore:
                        if delay > 0:
                            await asyncio.sleep(delay)
                        
                        logger.info(f"Worker fetching: {url} (Depth: {depth})")
                        page = await fetch(client, url)

                    if not page:
                        logger.warning(f"Worker failed to fetch: {url}")
                        async with cv:
                            active_workers -= 1
                            cv.notify_all()
                        continue

                    status = page.get("status")
                    
                    # Check if it's an external link
                    is_external = False
                    parsed_u = urlparse(url)
                    if frontier.base_domain and parsed_u.netloc and parsed_u.netloc != frontier.base_domain:
                        is_external = True

                    # If in broken links mode, we mainly care about Non-200s
                    if broken_links_only:
                        if status and status != 200:
                            results.append(page)
                            logger.info(f"Worker found broken link: {url} (Status: {status})")
                    else:
                        results.append(page)
                        logger.info(f"Worker fetched {url} (Status: {status}). Progress: {len(results)}/{limit}")

                    # Only parse if it's 200, not external, and within depth
                    if status == 200 and page.get("html") and not is_external and depth < max_depth:
                        extracted = parser(page["html"], page["url"], custom_selectors=custom_selectors)
                        
                        page["hreflangs"] = extracted.get("hreflangs", [])
                        page["images"] = extracted.get("images", [])
                        page["videos"] = extracted.get("videos", [])
                        page["canonical"] = extracted.get("canonical", "")
                        page["meta"] = extracted.get("meta", {})
                        page["headings"] = extracted.get("headings", {})
                        page["custom"] = extracted.get("custom", {})

                        for link in extracted.get("links", []):
                            graph.add_edge(page["url"], link)
                            
                            is_target_external = False
                            parsed_link = urlparse(link)
                            if frontier.base_domain and parsed_link.netloc and parsed_link.netloc != frontier.base_domain:
                                is_target_external = True
                                
                            # External links get max_depth+1 so they are fetched but never parsed
                            target_depth = max_depth + 1 if is_target_external else depth + 1
                            
                            # PRIORITIES: HTML (10), External (1)
                            priority = 1 if is_target_external else 10
                            frontier.add(link, depth=target_depth, force_add=is_target_external, priority=priority)
                            
                        if crawl_assets:
                            for asset in extracted.get("assets", []):
                                graph.add_edge(page["url"], asset)
                                # Assets: Priority 5
                                frontier.add(asset, depth=max_depth + 1, force_add=True, priority=5)

                finally:
                    async with cv:
                        active_workers -= 1
                        cv.notify_all()

        workers = [worker() for _ in range(concurrency)]
        await asyncio.gather(*workers)

    return results
