from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from src.crawler import crawl
from src.js_crawler import crawl_js_sync
from src.extractor import extract_metadata
from src.normalizer import normalize
from src.filter import is_valid
from src.generator import generate_sitemaps
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory=".", html=True), name="static")

app = FastAPI()
templates = Jinja2Templates(directory="templates")


def build_clean_urls(pages, fix_canonical=False):
    clean = set()

    for p in pages:
        meta = extract_metadata(p)

        if not is_valid(meta):
            continue

        chosen = meta["canonical"] if fix_canonical else meta["url"]
        clean.add(normalize(chosen))

    return list(clean)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
def generate(request: Request, domain: str = Form(...), limit: int = Form(200), use_js: bool = Form(False)):
def generate(
    return templates.TemplateResponse("index.html", {
    "request": request,
    "files": files,
    "count": len(clean_urls)
})
):
    if use_js:
        pages = crawl_js_sync(domain, limit=limit)
    else:
        pages = crawl(domain, limit=limit)

    clean_urls = build_clean_urls(pages, fix_canonical)

    files = generate_sitemaps(clean_urls, base_url=domain)

    return {
        "message": "Sitemap generated",
        "files": files,
        "count": len(clean_urls)
    }
