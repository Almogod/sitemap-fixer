import os
import time
import concurrent.futures
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# Core modules
from src.crawler_engine.crawler import crawl
from src.crawler_engine.js_crawler import crawl_js_sync  # optional fallback
from src.services.extractor import extract_metadata
from src.services.normalizer import normalize
from src.services.filter import is_valid
from src.services.generator import generate_sitemaps
from src.services.sitemap_parser import get_sitemap_urls
# Audit modules
from src.services.audit import generate_audit_report
from src.services.fixer import fix_urls, generate_fix_report
# Engine modules
from src.engine.engine import run_engine

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# -----------------------------
# PROGRESS TRACKING
# -----------------------------
progress_store = {}

@app.get("/progress")
def get_progress(task_id: str):
    return {"status": progress_store.get(task_id, "Starting..."), "progress": None}

# -----------------------------
# URL CLEANING LOGIC (IMPROVED)
# -----------------------------
def build_clean_urls(pages, fix_canonical=False):
    clean = set()

    for p in pages:
        meta = extract_metadata(p)

        if not is_valid(meta):
            continue

        chosen = meta["url"]

        if fix_canonical:
            canonical = meta.get("canonical")
            if canonical and canonical.startswith("http"):
                chosen = canonical

        # remove query params (important for SEO)
        chosen = chosen.split("?")[0]

        try:
            clean.add(normalize(chosen))
        except:
            continue

    return sorted(list(clean))


# -----------------------------
# HOME ROUTE
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -----------------------------
# MAIN GENERATE ROUTE
# -----------------------------
@app.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    domain: str = Form(...),
    limit: int = Form(50),
    use_js: bool = Form(False),
    fix_canonical: bool = Form(False),
    task_id: str = Form(None)
):
    try:
        if task_id: progress_store[task_id] = "Crawling website pages..."
        time.sleep(1.5)
        pages, graph = crawl(domain, limit=limit)
        # 2. Add sitemap URLs
        if task_id: progress_store[task_id] = "Checking existing sitemap..."
        time.sleep(1.5)
        sitemap_urls = get_sitemap_urls(domain)
        for url in sitemap_urls:
            pages.append({
                "url": url,
                "status": 200,
                "html": ""
            })

        # Sort pages to guarantee deterministic execution order later
        pages.sort(key=lambda x: x["url"])

        if task_id: progress_store[task_id] = "Cleaning URLs..."
        time.sleep(1.5)
        clean_urls = build_clean_urls(pages, fix_canonical)

        def engine_progress(msg):
            if task_id: progress_store[task_id] = msg
            time.sleep(1)

        engine_result = run_engine(pages, clean_urls, domain, graph, progress_callback=engine_progress)

        audit = engine_result["audit"]
        fixed_urls = engine_result["fixed_urls"]
        plan = engine_result["plan"]

        # Meta Results
        meta_results = engine_result["modules"].get("meta", {})
        meta_issues = meta_results.get("issues", [])
        meta_fixes = meta_results.get("fixes", {})

        # Internal Link Results
        internal_link_results = engine_result["modules"].get("internal_links", {})
        link_issues = internal_link_results.get("issues", {})
        link_suggestions = internal_link_results.get("suggestions", {})

        # Crawl Budget Results
        crawl_budget_results = engine_result["modules"].get("crawl_budget", {})
        crawl_budget_issues = crawl_budget_results.get("issues", {})
        crawl_budget_suggestions = crawl_budget_results.get("suggestions", [])

        #schema injector
        schema_results = engine_result["modules"].get("schema", {})
        schema_issues = schema_results.get("issues", [])
        schema_generated = schema_results.get("schemas", {})

        #Image SEO
        image_results = engine_result["modules"].get("image_seo", {})
        image_issues = image_results.get("issues", [])
        image_fixes = image_results.get("fixes", {})

        #Core web vitals
        core_results = engine_result["modules"].get("core_web_vitals", {})
        core_issues = core_results.get("issues", [])
        core_suggestions = core_results.get("suggestions", {})

        if task_id: progress_store[task_id] = "Writing output files..."
        time.sleep(1.5)
        files = generate_sitemaps(fixed_urls, base_url=domain)

        # 🔥 DEBUG PRINT
        print("AUDIT:", audit)
        print("META ISSUES:", meta_issues)
        print("LINK ISSUES:", link_issues)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "files": files,
            "count": len(fixed_urls),
            "audit": audit,
            "meta_issues": meta_issues,
            "meta_fixes": meta_fixes,
            "link_issues": link_issues,
            "link_suggestions": link_suggestions,
            "plan": plan
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e)
        })
    finally:
        if task_id and task_id in progress_store:
            del progress_store[task_id]


# -----------------------------
# DOWNLOAD ROUTE
# -----------------------------
@app.get("/download")
def download_file(file: str):
    file_path = os.path.abspath(file)
    return FileResponse(file_path, filename=os.path.basename(file_path))
