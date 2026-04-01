import os
import json
import sys
import asyncio
import time
import uuid
import concurrent.futures
from typing import Optional, Union
from datetime import datetime # Added for /health endpoint

from fastapi import FastAPI, Form, BackgroundTasks, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

start_time = time.time()

# Initialize Sentry
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
    )

# Core modules
from src.config import config
from src.utils.logger import logger, audit_logger
from src.services.auth import verify_token, admin_only
from src.services.batch_manager import batch_manager
from src.crawler_engine.crawler import crawl
from src.crawler_engine.js_crawler import crawl_js_sync
from src.utils.url_utils import build_clean_urls
from src.services.task_store import task_store
from src.services.sitemap_parser import get_sitemap_urls
from src.services.generator import generate_sitemaps
from src.engine.engine import run_engine
from src.automation.automation_engine import run_automation
from src.plugin.plugin_runner import run_plugin
from src.services.cache_service import cache_service
from src.utils.security import is_safe_path

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=config.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Prometheus setup
Instrumentator().instrument(app).expose(app)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__}
    )

@app.get("/progress")
def get_progress(task_id: str):
    task_info = task_store.get_status(task_id)
    return {
        "status": task_info.get("status_msg", "Starting..."),
        "state": task_info.get("status", "running"),
        "error": task_info.get("error", None)
    }

@app.get("/health")
def health_check():
    import psutil
    process = psutil.Process(os.getpid())
    return {
        "status": "healthy",
        "uptime": time.time() - start_time,
        "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
        "timestamp": datetime.utcnow().isoformat()
    }

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
            # Note: We need a slight modification to how 'crawl' passes arguments if we want to be strict
            # but for now we'll assume the scheduler.run_workers is what we want to tune.
            logger.info("Initializing frontier and graph with domain locking...")
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
            logger.info(f"Starting run_workers (Backend: {crawler_backend}, Max Depth: {max_depth}, Concurrency: {concurrency})...")
            pages = asyncio.run(run_workers(frontier, extract_links, graph, limit=limit, delay=delay, check_robots=check_robots, broken_links_only=broken_links_only, max_depth=max_depth, crawl_assets=crawl_assets, concurrency=concurrency, custom_selectors=custom_selectors))
        logger.info(f"Crawl completed. Found {len(pages)} pages.")
        
        task_store.set_status(task_id, "Checking existing sitemap...")
        sitemap_urls = get_sitemap_urls(domain)
        for url in sitemap_urls:
            if len(pages) >= limit:
                break
            # Avoid duplicates if they were already crawled
            if not any(p["url"] == url for p in pages):
                pages.append({"url": url, "status": 200, "html": "", "hreflangs": [], "images": [], "videos": []})

        pages.sort(key=lambda x: x.get("url", ""))

        task_store.set_status(task_id, "Cleaning URLs...")
        # Pre-process
        clean_urls = build_clean_urls(pages, fix_canonical)
        
        def engine_progress(msg):
            task_store.set_status(task_id, msg)

        # 1. Run Engine
        engine_result = run_engine(pages, clean_urls, domain, graph, progress_callback=engine_progress)

        # 2. Run Automation
        task_store.set_status(task_id, "Running Automations...")
        actions = engine_result.get("actions", [])
        
        automation_config = {
            "platform": config.AUTOMATION_PLATFORM,
            "github_token": config.GITHUB_TOKEN,
            "repo": config.GITHUB_REPO,
            "branch": config.GITHUB_BRANCH
        }
        automation_result = run_automation(actions, automation_config)

        # 3. Generate Files (Conditional)
        files = []
        if generate_sitemap:
            task_store.set_status(task_id, "Generating Sitemaps...")
            # Pass full page objects which now contain hreflang/media
            files = generate_sitemaps(pages, base_url=domain)
        else:
            task_store.set_status(task_id, "Skipping Sitemap Generation as requested.")

        # 4. Save Results
        task_store.set_status(task_id, "Finalizing...")
        final_results = {
            "files": files,
            "count": len(clean_urls),
            "engine_result": engine_result,
            "automation_result": automation_result,
            "analysis_mode": "standard",
            "sitemap_generated": generate_sitemap
        }
        task_store.save_results(task_id, final_results)
        cache_service.set(cache_key, final_results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        task_store.set_status(task_id, f"Error: {str(e)}", error=str(e))

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
@limiter.limit("100/15minutes")
def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    domain: str = Form(...),
    limit: int = Form(50),
    use_js: bool = Form(False),
    delay: float = Form(1.0),
    check_robots: bool = Form(True),
    generate_sitemap: bool = Form(True),
    broken_links_only: bool = Form(False),
    max_depth: int = Form(10),
    crawl_assets: bool = Form(False),
    crawler_backend: str = Form("memory"),
    concurrency: int = Form(10),
    custom_selectors: Optional[str] = Form(None),
    task_id: Optional[str] = Form(None)
):
    # Ensure at least 1 page
    limit = max(1, limit)
    if not task_id:
        task_id = str(uuid.uuid4())
    background_tasks.add_task(
        run_analysis_task, 
        task_id=task_id, 
        domain=domain, 
        limit=limit, 
        use_js=use_js, 
        fix_canonical=False,
        delay=delay,
        check_robots=check_robots,
        generate_sitemap=generate_sitemap,
        broken_links_only=broken_links_only,
        max_depth=max_depth,
        crawl_assets=crawl_assets,
        crawler_backend=crawler_backend,
        concurrency=concurrency,
        custom_selectors=json.loads(custom_selectors) if custom_selectors else None
    )
    return JSONResponse(content={"status": "started", "task_id": task_id})

# ─────────────────────────────────────────────────────────
# PLUGIN ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.post("/plugin/run")
@limiter.limit("20/15minutes")
def run_plugin_task(
    request: Request,
    background_tasks: BackgroundTasks,
    site_url: str = Form(...),
    competitors: str = Form(""),
    limit: int = Form(100),
    max_depth: int = Form(10),
    crawl_assets: bool = Form(False),
    crawler_backend: str = Form("memory"),
    openai_key: Optional[str] = Form(None),
    gemini_key: Optional[str] = Form(None),
    ollama_host: Optional[str] = Form(None),
    site_token: Optional[str] = Form(None),
    concurrency: int = Form(10),
    custom_selectors: Optional[str] = Form(None),
    task_id: Optional[str] = Form(None)
):
    # Ensure at least 1 page
    limit = max(1, limit)
    
    if not task_id:
        task_id = str(uuid.uuid4())[:10]
    task_store.set_status(task_id, "In Progress")
    
    comp_list = [c.strip() for c in competitors.split(",") if c.strip()]
    
    # Configure LLM
    llm_config = {
        "provider": "openai" if openai_key else ("gemini" if gemini_key else "ollama"),
        "api_key": openai_key or gemini_key,
        "ollama_host": ollama_host or "http://localhost:11434"
    }

    background_tasks.add_task(
        run_plugin, 
        site_url=site_url, 
        task_id=task_id,
        competitors=comp_list,
        llm_config=llm_config,
        crawl_options={
            "limit": limit, 
            "max_depth": max_depth, 
            "crawl_assets": crawl_assets, 
            "backend": crawler_backend,
            "concurrency": concurrency,
            "custom_selectors": json.loads(custom_selectors) if custom_selectors else None
        },
        site_token=site_token,
        deploy_config={} # Empty until approved
    )
    
    return JSONResponse(content={"status": "started", "task_id": task_id})

@app.post("/plugin/approve")
@limiter.limit("20/15minutes")
def approve_plugin_fixes(
    request: Request,
    background_tasks: BackgroundTasks,
    task_id: str = Form(...),
    approved_actions: str = Form(""), # comma separated IDs
    approved_pages: str = Form(""),   # comma separated keywords
    method: str = Form("github"),
    github_token: Optional[str] = Form(None),
    github_repo: Optional[str] = Form(None),
    github_branch: Optional[str] = Form("main"),
    vercel_token: Optional[str] = Form(None),
    vercel_project_id: Optional[str] = Form(None),
    vercel_team_id: Optional[str] = Form(None),
    hostinger_api_key: Optional[str] = Form(None),
    hostinger_host: Optional[str] = Form(None),
    hostinger_user: Optional[str] = Form(None),
    hostinger_site_id: Optional[str] = Form(None),
    ftp_host: Optional[str] = Form(None),
    ftp_user: Optional[str] = Form(None),
    ftp_pass: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    site_token: Optional[str] = Form(None)
):
    action_ids = [a.strip() for a in approved_actions.split(",") if a.strip()]
    page_keywords = [p.strip() for p in approved_pages.split(",") if p.strip()]

    # Sanitize github_repo
    if github_repo:
        github_repo = github_repo.strip().replace("https://github.com/", "").strip("/")
    
    deploy_config = {
        "platform": method,
        "github_token": github_token,
        "github_repo": github_repo,
        "github_branch": github_branch or "main",
        "vercel_token": vercel_token,
        "vercel_project_id": vercel_project_id,
        "vercel_team_id": vercel_team_id,
        "hostinger_api_key": hostinger_api_key,
        "hostinger_host": hostinger_host,
        "hostinger_user": hostinger_user,
        "hostinger_site_id": hostinger_site_id,
        "ftp_host": ftp_host,
        "ftp_user": ftp_user,
        "ftp_pass": ftp_pass,
        "webhook_url": webhook_url
    }
    
    from src.plugin.plugin_runner import apply_approved_plugin_fixes
    background_tasks.add_task(
        apply_approved_plugin_fixes,
        task_id=task_id,
        approved_action_ids=action_ids,
        approved_page_keywords=page_keywords,
        deploy_config=deploy_config,
        site_token=site_token
    )
    
    return JSONResponse(content={"status": "deployment_started", "task_id": task_id})

@app.get("/results", response_class=HTMLResponse)
def show_results(request: Request, task_id: str):
    task_info = task_store.get_status(task_id)
    
    if task_info.get("status") == "error":
        return templates.TemplateResponse("index.html", {"request": request, "error": task_info.get("error")})
        
    results = task_store.get_results(task_id)
    if not results:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Results not found or task incomplete."})

    is_plugin = "seo_score_before" in results
    engine_result = results.get("engine_result", {}) if is_plugin else results.get("engine_result", {})
    modules = engine_result.get("modules", {})
    
    ctx = {
        "request": request,
        "task_id": task_id,
        "is_plugin": is_plugin,
        "plugin_report": results if is_plugin else None,
        "engine_result": engine_result,
        "seo_score": results.get("seo_score_after") or engine_result.get("seo_score", 0),
        "actions": results.get("suggested_actions") or engine_result.get("actions", []),
        "meta_issues": modules.get("meta", {}).get("issues", []),
        "image_issues": modules.get("image_seo", {}).get("issues", []),
        "core_issues": modules.get("core_web_vitals", {}).get("issues", []),
        "speed_issues": modules.get("page_speed", {}).get("issues", []),
        "heading_issues": modules.get("heading_structure", {}).get("issues", []),
        "og_issues": modules.get("open_graph", {}).get("issues", []),
        "quality_issues": modules.get("content_quality", {}).get("issues", []),
        "mobile_issues": modules.get("mobile_seo", {}).get("issues", []),
        "experience_issues": modules.get("page_experience", {}).get("issues", []),
        "schema_issues": modules.get("structured_data_validator", {}).get("issues", []),
        "hreflang_issues": modules.get("hreflang", {}).get("issues", []),
        "link_issues": modules.get("broken_links", {}).get("issues", []),
        "keyword_gap": modules.get("keyword_gap", {}).get("keyword_gap", {}),
        "site_keywords": modules.get("keyword_gap", {}).get("site_keywords", []),
        "pages_generated": results.get("pages_generated", []),
        "active_tab": "plugin-tab" if is_plugin else "standard-tab"
    }
    
    return templates.TemplateResponse("index.html", ctx)

@app.get("/plugin/download_report")
def download_plugin_report(task_id: str):
    # Sanitize task_id to prevent path traversal
    if ".." in task_id or "/" in task_id or "\\" in task_id:
         raise HTTPException(status_code=400, detail="Invalid task_id")
         
    results = task_store.get_results(task_id)
    if not results:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    
    from src.utils.pdf_generator import generate_seo_pdf
    report_file = f"seo_report_{task_id}.pdf"
    file_path = os.path.join(os.getcwd(), report_file)
    
    generate_seo_pdf(results, file_path)
    return FileResponse(file_path, filename=report_file)

@app.post("/plugin/generate_content")
@limiter.limit("10/15minutes")
def generate_keyword_content(
    request: Request,
    background_tasks: BackgroundTasks,
    task_id: str = Form(...),
    keyword: str = Form(...),
    competitors: str = Form(""),
    openai_key: Optional[str] = Form(None),
    gemini_key: Optional[str] = Form(None),
    ollama_host: Optional[str] = Form(None)
):
    """
    Endpoint for targeted generation of a single page based on a keyword.
    """
    comp_list = [c.strip() for c in competitors.split(",") if c.strip()]
    llm_config = {
        "provider": "openai" if openai_key else ("gemini" if gemini_key else "ollama"),
        "api_key": openai_key or gemini_key,
        "ollama_host": ollama_host or "http://localhost:11434"
    }

    from src.content.engine import generate_content_for_keyword
    
    def run_gen():
        # Get existing pages for internal links
        results = task_store.get_results(task_id) or {}
        engine_res = results.get("engine_result", {})
        existing = [{"url": p["url"], "title": p.get("title", p["url"])} for p in engine_res.get("pages", [])]
        
        # Generate
        new_page = generate_content_for_keyword(keyword, comp_list, llm_config, existing)
        
        if "error" not in new_page:
            # Append to pages_generated in the report
            if "pages_generated" not in results:
                results["pages_generated"] = []
            
            results["pages_generated"].append({
                "keyword": keyword,
                "slug": new_page["slug"],
                "title": new_page["meta_title"],
                "word_count": new_page["word_count"],
                "html": new_page["html"],
                "approved": True
            })
            task_store.save_results(task_id, results)
            task_store.set_status(task_id, f"Generated content for: {keyword}")
        else:
            task_store.set_status(task_id, f"Failed to generate content for {keyword}: {new_page['error']}")

    background_tasks.add_task(run_gen)
    return JSONResponse(content={"status": "generation_started", "keyword": keyword})

@app.get("/download")
def download_file(file: str):
    base_dir = os.getcwd()
    if not is_safe_path(file, base_dir):
        raise HTTPException(status_code=403, detail="Access denied")
        
    file_path = os.path.abspath(os.path.join(base_dir, file))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path, filename=os.path.basename(file_path))
