import os
import concurrent.futures
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# Core modules
from src.crawler import crawl
from src.js_crawler import crawl_js_sync  # optional fallback
from src.extractor import extract_metadata
from src.normalizer import normalize
from src.filter import is_valid
from src.generator import generate_sitemaps
from src.sitemap_parser import get_sitemap_urls
# Audit modules
from src.audit import generate_audit_report

app = FastAPI()

templates = Jinja2Templates(directory="templates")


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

    return list(clean)


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
    limit: int = Form(50),  # increased slightly (safe for HTML crawler)
    use_js: bool = Form(False),
    fix_canonical: bool = Form(False),
):
    def run_js_task(target_domain, target_limit):
        return crawl_js_sync(target_domain, limit=target_limit)

    try:
        # -----------------------------
        # PRIMARY: SMART HTML CRAWL
        # -----------------------------
        pages = crawl(domain, limit=limit)

        # -----------------------------
        # ADD SITEMAP URLs (IMPORTANT)
        # -----------------------------
        sitemap_urls = get_sitemap_urls(domain)

        for url in sitemap_urls:
            pages.append({
                "url": url,
                "status": 200,
                "html": ""
            })

        # -----------------------------
        # OPTIONAL JS FALLBACK
        # -----------------------------
        if use_js and len(pages) < 5:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_js_task, domain, 15)

                try:
                    js_pages = future.result(timeout=60)
                    pages.extend(js_pages)
                except:
                    pass

        if not pages:
            return templates.TemplateResponse("index.html", {
                "request": request,
                "error": "No pages found. Site may block crawling."
            })

        # -----------------------------
        # CLEAN + GENERATE SITEMAP
        # -----------------------------
        clean_urls = build_clean_urls(pages, fix_canonical)

        audit = generate_audit_report(pages, clean_urls)

        files = generate_sitemaps(clean_urls, base_url=domain)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "files": files,
            "count": len(clean_urls)
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "files": files,
            "count": len(clean_urls),
            "audit": audit
        })


# -----------------------------
# DOWNLOAD ROUTE
# -----------------------------
@app.get("/download")
def download_file(file: str):
    file_path = os.path.abspath(file)
    return FileResponse(file_path, filename=os.path.basename(file_path))
