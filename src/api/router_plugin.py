from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from src.schemas.request import PluginRunRequest, PluginApproveRequest, KeywordGenerationRequest, ContentUpdateRequest
from src.services.task_store import task_store
from src.plugin.plugin_runner import run_plugin, apply_approved_plugin_fixes
from src.utils.logger import logger
from src.config import config
import uuid
import os
import json
from typing import Optional

router = APIRouter()

@router.post("/run")
async def run_plugin_task(
    data: PluginRunRequest,
    background_tasks: BackgroundTasks
):
    task_id = data.task_id or str(uuid.uuid4())[:10]
    task_store.set_status(task_id, "In Progress", domain=data.site_url)
    
    # ── API Key Merging Logic ────────────────────────────────────────
    # 1. Take from frontend (data)
    # 2. Fallback to .env (config)
    # 3. Use None if both are missing (Engine handles fallback to builtin)
    
    frontend_openai = data.openai_key.get_secret_value() if data.openai_key else None
    frontend_gemini = data.gemini_key.get_secret_value() if data.gemini_key else None
    
    final_openai = frontend_openai or (config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None)
    final_gemini = frontend_gemini or (config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None)
    final_ollama = data.ollama_host or config.OLLAMA_HOST
    
    # Determine primary provider based on availability
    if final_openai:
        provider = "openai"
        api_key = final_openai
    elif final_gemini:
        provider = "gemini"
        api_key = final_gemini
    elif final_ollama and "localhost" not in final_ollama: # Basic heuristic for active Ollama
        provider = "ollama"
        api_key = "ollama" # placeholder
    else:
        provider = "builtin"
        api_key = None

    llm_config = {
        "provider": provider,
        "api_key": api_key,
        "ollama_host": final_ollama,
        "openai_key": final_openai,
        "gemini_key": final_gemini
    }

    background_tasks.add_task(
        run_plugin, 
        site_url=data.site_url, 
        task_id=task_id,
        competitors=data.competitors or [],
        llm_config=llm_config,
        crawl_options={
            "limit": data.limit, 
            "max_depth": data.max_depth, 
            "crawl_assets": data.crawl_assets, 
            "backend": data.crawler_backend,
            "concurrency": data.concurrency,
            "custom_selectors": data.custom_selectors
        },
        site_token=None,
        deploy_config={} 
    )
    
    return JSONResponse(content={"status": "started", "task_id": task_id})

@router.post("/approve")
async def approve_plugin_fixes(
    data: PluginApproveRequest,
    background_tasks: BackgroundTasks
):
    deploy_config = data.deploy_config.dict() if data.deploy_config else {}
    for k, v in deploy_config.items():
        if hasattr(v, "get_secret_value"):
            deploy_config[k] = v.get_secret_value()

    report = task_store.get_results(data.task_id) or {}
    llm_config = report.get("llm_config")

    background_tasks.add_task(
        apply_approved_plugin_fixes,
        task_id=data.task_id,
        approved_action_ids=data.approved_actions,
        approved_page_keywords=data.approved_pages,
        deploy_config=deploy_config,
        llm_config=llm_config,
        site_token=None
    )
    
    return JSONResponse(content={"status": "deployment_started", "task_id": data.task_id})

@router.get("/download_report")
def download_plugin_report(task_id: str):
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

@router.post("/generate_content")
async def generate_keyword_content(
    data: KeywordGenerationRequest,
    background_tasks: BackgroundTasks
):
    from src.content.engine import generate_content_for_keyword
    
    # Merging logic for standalone generation
    final_openai = data.openai_key or (config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None)
    final_gemini = data.gemini_key or (config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None)
    final_ollama = data.ollama_host or config.OLLAMA_HOST
    
    provider = "openai" if final_openai else ("gemini" if final_gemini else "ollama")
    api_key = final_openai or final_gemini or (final_ollama if provider == "ollama" else None)

    llm_config = {
        "provider": provider,
        "api_key": api_key,
        "ollama_host": final_ollama
    }

    background_tasks.add_task(
        _run_and_save_keyword_content,
        task_id=data.task_id,
        keyword=data.keyword,
        competitors=data.competitors or [],
        llm_config=llm_config
    )
    
    return JSONResponse(content={"status": "generation_started", "task_id": data.task_id})

async def _run_and_save_keyword_content(task_id, keyword, competitors, llm_config):
    from src.content.engine import generate_content_for_keyword
    try:
        report = task_store.get_results(task_id) or {}
        pages = report.get("existing_pages_list", [])
        
        result = generate_content_for_keyword(keyword, competitors, llm_config, existing_pages=pages)
        
        if "error" not in result:
            if "pages_generated" not in report:
                report["pages_generated"] = []
            
            result["keyword"] = keyword
            report["pages_generated"].append(result)
            task_store.save_results(task_id, report)
            task_store.set_status(task_id, f"Generated content for {keyword}")
    except Exception as e:
        logger.error(f"Background generation failed: {e}")

@router.post("/update_content")
async def update_content(
    data: ContentUpdateRequest
):
    try:
        report = task_store.get_results(data.task_id)
        if not report:
            return JSONResponse(status_code=404, content={"error": "Task results not found"})
        
        updated_data = json.loads(data.schema_data)
        
        # Find and update the keyword content
        updated = False
        if "pages_generated" in report:
            for page in report["pages_generated"]:
                if page.get("keyword") == data.keyword:
                    page.update(updated_data)
                    updated = True
                    break
        
        if not updated:
            return JSONResponse(status_code=404, content={"error": "Keyword not found in results"})
            
        task_store.save_results(data.task_id, report)
        return JSONResponse(content={"status": "success", "message": f"Updated content for {data.keyword}"})
    except Exception as e:
        logger.error(f"Failed to update content: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
