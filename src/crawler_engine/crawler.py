import asyncio

from .frontier import URLFrontier, SQLiteURLFrontier
from .parser import extract_links
from .scheduler import run_workers
from .graph import CrawlGraph
from src.utils.logger import logger

def crawl(start_url, limit=200, extra_headers=None, max_depth=10, crawl_assets=False, backend="memory", concurrency=10, custom_selectors=None, broken_links_only=False):
    # Scaling logic: Auto-switch to SQLite for large crawls to prevent memory pressure
    if limit > 500 and backend == "memory":
        logger.info(f"Scaling detected (Limit: {limit}). Auto-switching to SQLite Enterprise Frontier...")
        backend = "sqlite"

    if backend == "sqlite":
        logger.info("Initializing SQLite Enterprise Frontier...")
        frontier = SQLiteURLFrontier(base_domain=start_url)
    else:
        logger.info("Initializing In-Memory Frontier...")
        frontier = URLFrontier(base_domain=start_url)
        
    frontier.add(start_url)
    
    # Initialize the graph
    graph = CrawlGraph()

    # Pass the graph into the scheduler/worker system
    try:
        pages = asyncio.run(
            run_workers(
                # ... args ...
                frontier, 
                extract_links, 
                graph, 
                start_url=start_url,
                limit=limit, 
                concurrency=concurrency,
                extra_headers=extra_headers,
                max_depth=max_depth,
                crawl_assets=crawl_assets,
                custom_selectors=custom_selectors,
                broken_links_only=broken_links_only
            )
        )
    except RuntimeError:
        # Fallback if a loop is already running in this thread
        loop = asyncio.new_event_loop()
        pages = loop.run_until_complete(
            run_workers(
                # ... args ...
                frontier, 
                extract_links, 
                graph, 
                start_url=start_url,
                limit=limit, 
                concurrency=concurrency,
                extra_headers=extra_headers,
                max_depth=max_depth,
                crawl_assets=crawl_assets,
                custom_selectors=custom_selectors,
                broken_links_only=broken_links_only
            )
        )

    return pages, graph
