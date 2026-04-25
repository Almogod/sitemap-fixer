import asyncio
import httpx
import json
from src.crawler_engine.fetcher import fetch
from src.utils.text_processor import clean_html, chunk_text
from src.content.page_generator import _call_openai, _call_gemini, _call_ollama, _extract_json_from_llm
from src.utils.llm_resolver import resolve_api_key, is_valid_key, call_llm_with_fallback
from src.config import config
from src.utils.logger import logger

async def process_site_homepage(url: str):
    """
    Scrapes the homepage, cleans it, chunks it, and structures the business analysis.
    """
    logger.info(f"Analysis Pipeline: Starting process for {url}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        result = await fetch(client, url)
        
    if result.get("status") != 200:
        logger.error(f"Failed to fetch {url}: {result.get('error')}")
        return {"error": f"Failed to fetch: {result.get('status')}"}
    
    html = result.get("html", "")
    return await process_html_content(url, html)

async def process_html_content(url: str, html: str, llm_config: dict = None):
    """
    Cleans, chunks, and structures the business analysis from provided HTML.
    Uses 'minimal' cleaning to preserve nav/header context for business intelligence.
    """
    clean_text = clean_html(html, minimal=True)
    chunks = chunk_text(clean_text, chunk_size=6000)
    
    logger.info(f"Extracted {len(chunks)} chunks for analysis.")
    
    structured_data = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
        extracted = await structure_business_chunk(chunk, llm_config)
        if extracted:
            structured_data.append(extracted)
            
    return {
        "url": url,
        "raw_text_length": len(clean_text),
        "chunk_count": len(chunks),
        "structured_data": structured_data
    }

async def process_raw_content(url: str, text: str, llm_config: dict = None):
    """
    Chunks and structures the business analysis from provided raw text (e.g. Github Repo source).
    """
    chunks = chunk_text(text, chunk_size=6000)
    
    logger.info(f"Extracted {len(chunks)} chunks from raw text for analysis.")
    
    structured_data = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
        extracted = await structure_business_chunk(chunk, llm_config)
        if extracted:
            structured_data.append(extracted)
            
    return {
        "url": url,
        "raw_text_length": len(text),
        "chunk_count": len(chunks),
        "structured_data": structured_data
    }

async def structure_business_chunk(chunk: str, llm_config: dict = None):
    """
    Sends a chunk to the LLM to extract business-specific data points.
    Uses cascading API key resolution — if one field is empty, checks others.
    """
    prompt = f"""### BUSINESS INTELLIGENCE EXTRACTION ###
Extract high-fidelity business signals from this website chunk. We need the "Brand Touch" — what makes them unique.

CHUNK CONTENT:
{chunk}

EXTRACTION RULES:
1. "core_services": ACTUAL service/product names (not generic categories).
2. "brand_personality": Adjectives describing the "Touch" or "Feel" (e.g., Gritty, Elite, Compassionate, High-Tech).
3. "value_propositions": Specific unique selling points.
4. "target_audience": Who is the EXACT person they are talking to?
5. "technologies_mentioned": Tools, platforms, stacks mentioned.
6. "company_info": Brand name and stated mission.
7. "tonality": How do they talk? (e.g. "Direct and Technical", "Warm and Welcoming").

STRICT JSON OUTPUT:
{{
  "company_info": {{
    "name": "brand name",
    "mission": "stated mission"
  }},
  "brand_personality": ["adj1", "adj2"],
  "tonality": "description of voice",
  "core_services": ["specific service 1", "specific service 2"],
  "value_propositions": ["VP 1", "VP 2"],
  "target_audience": ["Segment 1"],
  "technologies_mentioned": ["Tech 1"],
  "key_findings": ["Any other unique touch markers or facts"]
}}
"""
    
    if not llm_config:
        llm_config = {
            "provider": config.LLM_PROVIDER,
            "api_key": config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None,
            "gemini_key": config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None,
            "model": "gpt-4o-mini" if config.LLM_PROVIDER == "openai" else "gemini-1.5-flash"
        }
    
    # Use centralized resolver — cascading field fallback
    resolved_provider, resolved_key = resolve_api_key(llm_config)
    
    if not is_valid_key(resolved_key) and resolved_provider != "ollama":
        logger.warning("No valid LLM key found for chunk structuring. Skipping.")
        return _heuristic_chunk_extraction(chunk)

    call_config = llm_config.copy()
    call_config["provider"] = resolved_provider
    call_config["api_key"] = resolved_key
    
    # Set appropriate model
    if resolved_provider == "openai":
        call_config["model"] = call_config.get("model", "gpt-4o-mini")
    elif resolved_provider == "gemini":
        call_config["model"] = call_config.get("model", "gemini-1.5-flash")

    try:
        raw_res = ""
        if resolved_provider == "openai":
            raw_res = _call_openai(prompt, call_config)
        elif resolved_provider == "gemini":
            raw_res = _call_gemini(prompt, call_config)
        elif resolved_provider == "ollama":
            raw_res = _call_ollama(prompt, call_config)
        elif resolved_provider == "openrouter":
            from src.content.page_generator import _call_openrouter
            raw_res = _call_openrouter(prompt, call_config)
            
        result = _extract_json_from_llm(raw_res)
        if result:
            return result
        
        # If JSON extraction failed, try heuristic
        return _heuristic_chunk_extraction(chunk)
    except Exception as e:
        logger.error(f"Chunk structuring failed: {e}")
        return _heuristic_chunk_extraction(chunk)


def _heuristic_chunk_extraction(chunk: str) -> dict:
    """
    Fallback: Extract business signals from chunk using regex and heuristics.
    Used when no LLM is available.
    """
    import re
    
    services = []
    technologies = []
    emails = []
    
    # Extract emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, chunk)
    
    # Extract technology mentions
    tech_keywords = [
        "React", "Angular", "Vue", "Node.js", "Python", "Django", "Flask",
        "AWS", "Azure", "Google Cloud", "GCP", "Docker", "Kubernetes",
        "PostgreSQL", "MongoDB", "Redis", "MySQL", "GraphQL", "REST",
        "TypeScript", "JavaScript", "Java", "Go", "Rust", "PHP",
        "Terraform", "Jenkins", "GitHub Actions", "GitLab CI",
        "WordPress", "Shopify", "WooCommerce", "Magento",
        "TensorFlow", "PyTorch", "OpenAI", "LangChain",
        "Figma", "Sketch", "Adobe", "Photoshop",
        "Salesforce", "HubSpot", "Stripe", "Twilio",
    ]
    chunk_lower = chunk.lower()
    for tech in tech_keywords:
        if tech.lower() in chunk_lower:
            technologies.append(tech)
    
    # Extract service-like phrases (sentences with action verbs + nouns)
    service_patterns = [
        r'(?:we |our team |we\'re )?(?:offer|provide|specialize|deliver|build|create|develop|design|manage|consult)[s]?\s+(?:in\s+)?([^.]{10,60})',
    ]
    for pattern in service_patterns:
        matches = re.findall(pattern, chunk_lower)
        services.extend([m.strip().title() for m in matches[:5]])
    
    return {
        "core_services": services[:5],
        "value_propositions": [],
        "target_audience": [],
        "technologies_mentioned": technologies,
        "company_info": {
            "name": "",
            "mission": "",
            "contact_info": emails[:3]
        },
        "key_findings": []
    }
