import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# Importing your custom modules
from src.crawler import crawl
from src.js_crawler import crawl_js_sync
from src.extractor import extract_metadata
from src.normalizer import normalize
from src.filter import is_valid
from src.generator import generate_sitemaps

app = FastAPI()

# Setup templates directory using Jinja2
templates = Jinja2Templates(directory="templates")


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

        try:
            clean.add(normalize(chosen))
        except:
            continue

    return list(clean)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    domain: str = Form(...),
    limit: int = Form(200),
    use_js: bool = Form(False),
    fix_canonical: bool = Form(False),
):

try:
    if use_js:
        pages = crawl_js_sync(domain, limit=limit)
    else:
        pages = crawl(domain, limit=limit)

    clean_urls = build_clean_urls(pages, fix_canonical)
    files = generate_sitemaps(clean_urls, base_url=domain)


except Exception as e:
    return templates.TemplateResponse("index.html", {
        "request": request,
        "error": str(e)
    })

@app.get("/download")
def download_file(path: str):
    return FileResponse(path=path, filename=os.path.basename(path))
