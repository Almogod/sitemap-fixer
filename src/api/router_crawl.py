from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from src.schemas.request import GenerateRequest
from src.services.task_store import task_store
from src.services.generator import generate_sitemaps
from src.services.sitemap_parser import get_sitemap_urls
from src.utils.url_utils import build_clean_urls
from src.crawler_engine.js_crawler import crawl_js_sync
from src.engine.engine import run_engine
from src.automation.automation_engine import run_automation
from src.services.cache_service import cache_service
from src.utils.logger import logger
from src.config import config
import uuid
import asyncio
from urllib.parse import urlparse

router = APIRouter()

def run_analysis_task(task_id: str, domain: str, limit: int, use_js: bool, fix_canonical: bool, delay: float = 1.0, check_robots: bool = True, generate_sitemap: bool = True, broken_links_only: bool = False, max_depth: int = 10, crawl_assets: bool = False, crawler_backend: str = "memory", concurrency: int = 10, custom_selectors: dict = None):
    try:
        cache_key = f"analysis:{domain}:{limit}"
        cached_res = cache_service.get(cache_key)
        if cached_res:
             task_store.set_status(task_id, "Completed (from cache)")
             task_store.save_results(task_id, cached_res)
             return

        logger.info(f"Starting crawl for {domain} with limit {limit} (JS: {use_js})...")
        if use_js:
            pages = crawl_js_sync(domain, limit=limit, delay=delay, check_robots=check_robots)
            graph = None
        else:
            from src.crawler_engine.frontier import URLFrontier, SQLiteURLFrontier
            from src.crawler_engine.parser import extract_links
            from src.crawler_engine.scheduler import run_workers
            from src.crawler_engine.graph import CrawlGraph
            
            if crawler_backend == "sqlite":
                frontier = SQLiteURLFrontier(base_domain=domain)
            else:
                frontier = URLFrontier(base_domain=domain)
                
            frontier.add(domain)
            graph = CrawlGraph()
            pages = asyncio.run(run_workers(frontier, extract_links, graph, limit=limit, delay=delay, check_robots=check_robots, broken_links_only=broken_links_only, max_depth=max_depth, crawl_assets=crawl_assets, concurrency=concurrency, custom_selectors=custom_selectors))
        
        task_store.set_status(task_id, "Checking existing sitemap...")
        sitemap_urls = get_sitemap_urls(domain)
        for url in sitemap_urls:
            if len(pages) >= limit: break
            if not any(p["url"] == url for p in pages):
                pages.append({"url": url, "status": 200, "html": "", "hreflangs": [], "images": [], "videos": []})

        pages.sort(key=lambda x: x.get("url", ""))
        
        base_path = urlparse(domain).path
        if base_path and base_path != "/":
            pages = [p for p in pages if urlparse(p.get("url", "")).path.startswith(base_path) or urlparse(p.get("url", "")).path == base_path]
            
        clean_urls = build_clean_urls(pages, fix_canonical)
        
        def engine_progress(msg):
            task_store.set_status(task_id, msg)

        engine_result = run_engine(pages, clean_urls, domain, graph, progress_callback=engine_progress)

        task_store.set_status(task_id, "Running Automations...")
        automation_config = {
            "platform": config.AUTOMATION_PLATFORM,
            "github_token": config.GITHUB_TOKEN.get_secret_value() if config.GITHUB_TOKEN else None,
            "repo": config.GITHUB_REPO,
            "branch": config.GITHUB_BRANCH
        }
        automation_result = run_automation(engine_result.get("actions", []), automation_config)

        files = []
        if generate_sitemap:
            task_store.set_status(task_id, "Generating Sitemaps...")
            files = generate_sitemaps(pages, base_url=domain)

        final_results = {
            "files": files,
            "count": len(clean_urls),
            "engine_result": engine_result,
            "automation_result": automation_result,
            "sitemap_generated": generate_sitemap
        }
        task_store.save_results(task_id, final_results)
        cache_service.set(cache_key, final_results)

    except Exception as e:
        logger.error(f"Error in analysis task: {str(e)}")
        task_store.set_status(task_id, f"Error: {str(e)}", error=str(e))

@router.post("/generate")
async def generate(
    data: GenerateRequest,
    background_tasks: BackgroundTasks
):
    task_id = data.task_id or str(uuid.uuid4())
    background_tasks.add_task(
        run_analysis_task, 
        task_id=task_id, 
        domain=data.domain, 
        limit=data.limit, 
        use_js=data.use_js, 
        fix_canonical=False,
        delay=data.delay,
        check_robots=data.check_robots,
        generate_sitemap=data.generate_sitemap,
        broken_links_only=data.broken_links_only,
        max_depth=data.max_depth,
        crawl_assets=data.crawl_assets,
        crawler_backend=data.crawler_backend,
        concurrency=data.concurrency,
        custom_selectors=data.custom_selectors
    )
    return JSONResponse(content={"status": "started", "task_id": task_id})
