import os
import json
import sys
import asyncio
import time
import uuid
import concurrent.futures
from typing import Optional, Union
from urllib.parse import urlparse
from datetime import datetime # Added for /health endpoint
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, BackgroundTasks, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
from src.services.task_store import task_store
from src.utils.security import is_safe_path

# schemas
from src.schemas.request import GenerateRequest, PluginRunRequest, PluginApproveRequest
from src.schemas.response import TaskStatusResponse

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Heavy initialization happens here after server start
    task_store.init()
    logger.info("UrlForge Engine fully initialized")
    yield

# Initialize FastAPI
app = FastAPI(
    title=config.APP_NAME,
    docs_url="/docs" if config.APP_ENV != "enterprise" else None,
    redoc_url="/redoc" if config.APP_ENV != "enterprise" else None,
    lifespan=lifespan
)
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

# No-Cache Middleware (Ensures 200 OK instead of 304 in Dev)
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static") or config.APP_ENV != "production":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if config.APP_ENV == "enterprise":
        logger.error(f"Unhandled error: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"error": "An internal server error occurred. Please contact support."}
        )
    
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__}
    )

# ─────────────────────────────────────────────────────────
# API ROUTERS
# ─────────────────────────────────────────────────────────
from src.api.router_tasks import router as tasks_router
from src.api.router_crawl import router as crawl_router
from src.api.router_plugin import router as plugin_router
from src.api.router_gsc import router as gsc_router

app.include_router(tasks_router, tags=["Tasks"])
app.include_router(crawl_router, tags=["Crawl"])
app.include_router(plugin_router, prefix="/plugin", tags=["Plugin"])
app.include_router(gsc_router, tags=["GSC"])

# Auth layer removed by user request

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "timestamp": int(time.time())})

@app.get("/results", response_class=HTMLResponse)
def show_results(request: Request, task_id: str):
    task_info = task_store.get_status(task_id)
    
    if task_info.get("state") == "error":
        return templates.TemplateResponse("index.html", {"request": request, "error": task_info.get("error"), "timestamp": int(time.time())})
        
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
        "site_keywords": results.get("site_keywords", []) if is_plugin else modules.get("keyword_gap", {}).get("site_keywords", []),
        "site_analysis_report": results.get("site_analysis_report"),
        "pages_generated": results.get("pages_generated", []),
        "active_tab": "plugin-tab" if is_plugin else "standard-tab",
        "timestamp": int(time.time())
    }
    
    return templates.TemplateResponse("index.html", ctx)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
