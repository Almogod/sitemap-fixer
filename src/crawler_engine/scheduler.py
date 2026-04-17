import asyncio
import httpx
import time
import base64
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from .fetcher import fetch
from src.config import config
from src.utils.logger import logger


async def run_workers(frontier, parser, graph, start_url=None, progress_callback=None, limit=200, concurrency=10, delay=1.0, check_robots=True, extra_headers=None, broken_links_only=False, max_depth=10, crawl_assets=False, custom_selectors=None, user_agent="chrome"):
    results = []
    class USER_AGENTS:
        chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        googlebot = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        googlebot_mobile = "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        bingbot = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
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
    # Map user agent string
    ua_string = getattr(USER_AGENTS, user_agent, USER_AGENTS.chrome) if hasattr(USER_AGENTS, user_agent) else user_agent
    headers["User-Agent"] = ua_string
    
    if extra_headers: headers.update(extra_headers)

    async with httpx.AsyncClient(timeout=config.CRAWL_TIMEOUT, headers=headers, mounts=mounts, follow_redirects=False) as client:
        semaphore = asyncio.Semaphore(concurrency)
        cv = asyncio.Condition()
        active_workers = 0
        checked_pages = 0

        async def worker():
            nonlocal active_workers, checked_pages
            while True:
                item = None
                async with cv:
                    # Wait for either: frontier has items, limit reached, or all workers idle
                    while not frontier.size() and checked_pages < limit:
                        if active_workers == 0:
                            cv.notify_all()
                            return
                        try:
                            await asyncio.wait_for(cv.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            # Re-check conditions after timeout
                            if not frontier.size() and active_workers == 0:
                                cv.notify_all()
                                return
                            continue
                    
                    if checked_pages >= limit:
                        cv.notify_all()
                        return
                    
                    item = frontier.get()
                    if item:
                        active_workers += 1
                        checked_pages += 1
                        if progress_callback and checked_pages % 10 == 0:
                            progress_callback(f"Active Crawl: {checked_pages}/{limit} pages checked")

                if not item: continue

                url = item["url"]
                depth = item["depth"]
                priority = item.get("priority", 0)

                try:
                    # Robots check
                    if rp and not rp.can_fetch("*", url):
                        logger.warning(f"Skipping {url} (Blocked by robots.txt)")
                        # Don't 'continue' - fall through to finally to decrement active_workers
                        async with cv:
                            active_workers -= 1
                            cv.notify_all()
                        continue

                    async with semaphore:
                        if delay > 0: await asyncio.sleep(delay)
                        # We handle redirects manually for strict domain locking
                        page = await fetch(client, url, follow_redirects=False)

                    if not page:
                        async with cv:
                            active_workers -= 1
                            cv.notify_all()
                        continue
                    
                    status = page.get("status")
                    final_url = page.get("final_url", url)
                    parsed_final = urlparse(final_url)
                    
                    # ENFORCE DOMAIN LOCKING ON FINAL DESTINATION
                    is_external = frontier.base_domain and parsed_final.netloc and not is_internal_domain(parsed_final.netloc, frontier.base_domain)

                    # Metadata init
                    page.update({"meta": {}, "headings": {}, "images": [], "videos": [], "hreflangs": [], "custom": {}, "canonical": ""})

                    # Handle Redirects (Manually)
                    if status in [301, 302, 303, 307, 308]:
                        location = page.get("headers", {}).get("location")
                        if location:
                            from urllib.parse import urljoin
                            target_url = urljoin(url, location)
                            parsed_target = urlparse(target_url)
                            target_is_ext = frontier.base_domain and parsed_target.netloc and not is_internal_domain(parsed_target.netloc, frontier.base_domain)
                            
                            if target_is_ext:
                                logger.info(f"Test found external redirect: {url} -> {target_url} (Stopped)")
                                page["redirect_to_external"] = target_url
                            else:
                                 logger.info(f"Following internal redirect: {url} -> {target_url}")
                                 frontier.add(target_url, depth=depth, priority=priority + 1) # High priority for redirects
                                 async with cv:
                                     cv.notify_all()
                        
                    if broken_links_only:
                        if (url == comp_url) or (status and status not in [200, 304]):
                            results.append(page)
                            logger.info(f"Fetched {url} ({status}). Broken links found: {len(results)}")
                        else:
                            logger.info(f"Fetched {url} ({status}). Skipped OK link.")
                    else:
                        results.append(page)
                        logger.info(f"Fetched {url} ({status}). Progress: {checked_pages}/{limit}")

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
                            # FIX: Domain enforcement for outgoing links
                            is_target_ext = frontier.base_domain and parsed_link.netloc and not is_internal_domain(parsed_link.netloc, frontier.base_domain)
                            if is_target_ext:
                                # We only "record" external links, we don't ADD them to queue for crawling
                                # This prevents the crawler from leaving the site.
                                pass 
                            else:
                                frontier.add(link, depth=depth + 1, priority=10)
                                async with cv:
                                    cv.notify_all()
                            
                        if crawl_assets:
                            for asset in extracted.get("assets", []):
                                graph.add_edge(page["url"], asset)
                                frontier.add(asset, depth=max_depth + 1, force_add=True, priority=5)
                                async with cv:
                                    cv.notify_all()
                except Exception as e:
                    logger.error(f"Worker Error: {e}")
                finally:
                    async with cv:
                        active_workers -= 1
                        cv.notify_all()

        workers = [worker() for _ in range(concurrency)]
        await asyncio.gather(*workers)

    return results

