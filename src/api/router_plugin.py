from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from src.schemas.request import PluginRunRequest, PluginApproveRequest, KeywordGenerationRequest, ContentUpdateRequest, StandaloneContentRequest, FAQUpdateRequest
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
    
    # Pre-validation: Catch accidental key-in-url-field swaps
    if data.site_url.startswith("AIza") or data.site_url.startswith("sk-"):
        raise HTTPException(status_code=400, detail=f"Invalid Site URL: It looks like you entered an API key ('{data.site_url[:8]}...') in the URL field.")
        
    # ── API Key Merging & Provider Selection ──────────────────────────
    frontend_openai = data.openai_key.get_secret_value() if data.openai_key else None
    frontend_gemini = data.gemini_key.get_secret_value() if data.gemini_key else None
    frontend_openrouter = data.openrouter_key.get_secret_value() if data.openrouter_key else None
    
    final_openai = frontend_openai or (config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None)
    final_gemini = frontend_gemini or (config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None)
    final_openrouter = frontend_openrouter or os.getenv("OPENROUTER_API_KEY")
    final_ollama = data.ollama_host or config.OLLAMA_HOST

    # ── Selection & Fallback Logic ────────────────────────────────────
    # User's Explicit Choice is the Starting Point
    provider = data.primary_provider or "gemini"
    api_key = None

    # Helper to check if a key is "real" (not a placeholder)
    def is_valid(k): return k and "your_" not in k and len(k) > 10

    # 1. Attempt the User's Choice
    if provider == "openai" and is_valid(final_openai): api_key = final_openai
    elif provider == "gemini" and is_valid(final_gemini): api_key = final_gemini
    elif provider == "openrouter" and is_valid(final_openrouter): api_key = final_openrouter
    elif provider == "ollama": api_key = "ollama"

    # 2. Automated Fallback Chain (if choice is unavailable)
    if not api_key:
        if is_valid(final_openai): 
            provider, api_key = "openai", final_openai
        elif is_valid(final_gemini): 
            provider, api_key = "gemini", final_gemini
        elif is_valid(final_openrouter): 
            provider, api_key = "openrouter", final_openrouter
        else:
            provider, api_key = "ollama", "ollama"
            
    logger.info(f"Engine selected provider: {provider} (Lead: {data.primary_provider})")

    # ── API Key Pre-Validation ──────────────────────────────────────
    if provider == "gemini" and api_key and api_key.startswith("AIza"):
        import google.generativeai as genai
        try:
            genai.configure(api_key=api_key)
            # Just test the connection
            list(genai.list_models())
        except Exception as e:
            err_msg = f"Gemini API Key Validation Failed: {str(e)}. Please check your key at aistudio.google.com."
            if "404" in str(e) or "403" in str(e):
                 err_msg = f"Gemini API Error: Your key is either invalid or the 'Generative Language API' is not enabled. (Details: {str(e)})"
            raise HTTPException(status_code=400, detail=err_msg)
    elif provider == "gemini" and api_key and "your_aiza" in api_key:
        # User left placeholder, but chose Gemini. We'll let it fail later or use fallback
        pass
    elif provider == "ollama":
        import httpx
        try:
            host = final_ollama.rstrip('/')
            models_res = httpx.get(f"{host}/api/tags", timeout=5.0)
            if models_res.status_code == 200:
                available = [m['name'] for m in models_res.json().get('models', [])]
                if not available:
                    raise HTTPException(status_code=400, detail="No Ollama models found. Please run 'ollama pull' to get a local model.")
                
                # If user didn't specify a model, or it's just the default string, use the first one available
                if not data.ollama_model or data.ollama_model == "llama3":
                    data.ollama_model = available[0]
                    logger.info(f"Ollama: Utilizing locally available model: '{data.ollama_model}'")
                
                # Ensure the selected model actually exists
                if not any(data.ollama_model in m for m in available):
                     data.ollama_model = available[0]
                     logger.info(f"Ollama: Requested model not found. Utilizing: '{data.ollama_model}'")
            else:
                 raise HTTPException(status_code=400, detail=f"Ollama returned error {models_res.status_code}")
        except Exception as e:
            logger.error(f"Ollama connection/discovery failed: {e}")
            raise HTTPException(status_code=400, detail=f"Ollama Error: Could not verify models at {final_ollama}. Details: {str(e)}")
        api_key = "ollama"

    task_store.set_status(task_id, "In Progress", domain=data.site_url)

    llm_config = {
        "provider": provider,
        "api_key": api_key,
        "ollama_host": final_ollama,
        "ollama_model": data.ollama_model or "llama3",
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
            "use_js": data.use_js,
            "delay": data.delay,
            "custom_selectors": data.custom_selectors,
            "broken_links_only": data.broken_links_only,
            "user_agent": data.user_agent
        },
        target_keyword=data.target_keyword,
        site_token=None,
        deploy_config={} 
    )
    
    return JSONResponse(content={"status": "started", "task_id": task_id})


@router.post("/approve")
async def approve_plugin_fixes(
    data: PluginApproveRequest,
    background_tasks: BackgroundTasks
):
    deploy_config = {}
    if data.deploy_config:
        # Use model_dump to get raw values, then reveal any SecretStr fields
        raw = data.deploy_config.model_dump()
        for k, v in raw.items():
            if hasattr(v, "get_secret_value"):
                deploy_config[k] = v.get_secret_value()
            elif v is not None:
                deploy_config[k] = v

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
        logger.error(f"Error in analysis task: {str(e)}")
        # Check if the domain looks like an API key (common user mistake)
        domain = report.get("domain", "") if report else ""
        if domain.startswith("AIza") or domain.startswith("sk-"):
             err_msg = f"Invalid Target Domain: It looks like you entered an API key ('{domain[:8]}...') instead of a website URL."
             task_store.set_status(data.task_id, err_msg, error=err_msg)
        else:
             task_store.set_status(data.task_id, f"Error: {str(e)}", error=str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/update_faq")
async def update_plugin_faq(data: FAQUpdateRequest):
    """Update a specific FAQ in the task result report."""
    report = task_store.get_results(data.task_id)
    if not report:
        raise HTTPException(status_code=404, detail="Task result not found")
    
    faqs = report.get("site_faqs", [])
    if 0 <= data.faq_index < len(faqs):
        faqs[data.faq_index] = {"question": data.question, "answer": data.answer}
        report["site_faqs"] = faqs
        task_store.save_results(data.task_id, report)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=400, detail="Invalid FAQ index")

@router.post("/delete_faq")
async def delete_plugin_faq(task_id: str, faq_index: int):
    """Remove an FAQ from the task result report."""
    report = task_store.get_results(task_id)
    if not report:
        raise HTTPException(status_code=404, detail="Task result not found")
    
    faqs = report.get("site_faqs", [])
    if 0 <= faq_index < len(faqs):
        faqs.pop(faq_index)
        report["site_faqs"] = faqs
        task_store.save_results(task_id, report)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=400, detail="Invalid FAQ index")
async def _run_and_save_keyword_content(task_id, keyword, competitors, llm_config):
    """Background task to generate content and update the report."""
    from src.content.engine import generate_content_for_keyword
    
    try:
        report = task_store.get_results(task_id)
        if not report:
            logger.error(f"Task {task_id} not found in store for background generation.")
            return

        domain_context = report.get("domain_context", {})
        existing_pages = report.get("existing_pages_list", [])
        site_wide_faqs = report.get("site_faqs", [])

        result = generate_content_for_keyword(
            keyword=keyword,
            competitor_urls=competitors,
            llm_config=llm_config,
            existing_pages=existing_pages,
            domain_context=domain_context,
            site_wide_faqs=site_wide_faqs
        )

        if "error" not in result:
            result["keyword"] = keyword
            if "pages_generated" not in report:
                report["pages_generated"] = []
            
            # Check if keyword already exists, if so update it
            found = False
            for idx, p in enumerate(report["pages_generated"]):
                if p.get("keyword") == keyword:
                    report["pages_generated"][idx] = result
                    found = True
                    break
            
            if not found:
                report["pages_generated"].append(result)
                
            task_store.save_results(task_id, report)
            logger.info(f"Successfully generated and saved content for '{keyword}' in task {task_id}")
        else:
            logger.error(f"Background generation failed for '{keyword}': {result['error']}")
            
    except Exception as e:
        logger.error(f"Critical error in background content generation: {e}", exc_info=True)
