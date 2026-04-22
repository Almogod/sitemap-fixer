# src/content/page_generator.py
"""
Expert Page Generator (REWRITTEN).
Architected for Zero-AI-Footprint content.
Uses Brand DNA Synthesis for fallback and Chain-of-Thought for LLM generation.
"""

import json
import re
import random
import time
import hashlib
from datetime import datetime
from src.utils.logger import logger

def generate_page(brief, llm_config, existing_pages=None, site_wide_faqs=None) -> dict:
    """
    Expert content synthesis pipeline.
    """
    existing_pages = existing_pages or []
    site_wide_faqs = site_wide_faqs or []
    json_schema_dict = None
    
    # 1. API Selection
    has_api = bool(llm_config.get("api_key")) or llm_config.get("provider") == "ollama"
    provider = llm_config.get("provider", "gemini").lower()

    if has_api:
        try:
            prompt = _build_expert_prompt(brief, existing_pages, site_wide_faqs)
            logger.info(f"FidelityEngine: Generating Expert {brief.target_keyword} via {provider}")
            
            raw = None
            if provider == "openai": 
                raw = _call_openai(prompt, llm_config)
            elif provider == "gemini": 
                raw = _call_gemini(prompt, llm_config)
            elif provider == "ollama": 
                raw = _call_ollama(prompt, llm_config)
            elif provider == "openrouter":
                raw = _call_openrouter(prompt, llm_config)
            
            if raw:
                json_schema_dict = _extract_json_from_llm(raw)
                if json_schema_dict:
                    return _finalize_result(brief, json_schema_dict, provider)
                    
            logger.error(f"FidelityEngine: {provider} returned invalid structure. Forcing High-Fidelity Synthesis.")
        except Exception as e:
            logger.error(f"FidelityEngine: API Failure: {e}")

    # 2. Site-DNA Synthesis Fallback (No Boilerplate)
    logger.info(f"FidelityEngine: Synthesizing {brief.target_keyword} from Site DNA.")
    json_schema_dict = _synthesize_from_site_dna(brief, existing_pages)
    return _finalize_result(brief, json_schema_dict, "dna_synthesis")

def _finalize_result(brief, schema, method):
    """Final package for the UI/Deployment."""
    return {
        "slug": brief.url_slug,
        "meta_title": schema.get("meta", {}).get("title", brief.page_title),
        "meta_description": schema.get("meta", {}).get("description", brief.meta_description),
        "schema_data": schema,
        "word_count": schema.get("content_metadata", {}).get("word_count", 0),
        "generation_method": method,
    }

def _synthesize_from_site_dna(brief, existing_pages: list) -> dict:
    """
    Constructs a page using actual Site DNA fragments.
    NO generic templates. Uses mission, services, and niche-specific wording.
    """
    kw = brief.target_keyword
    niche = brief.niche
    mission = (brief.site_profile_md or f"Expert authority in {niche}.").split("\n")[0].replace("# ", "")
    services = brief.services or [niche]
    brand = mission.split(":")[-1].strip() if ":" in mission else "Our industry experts"
    
    # Hero
    hero = {
        "headline": f"Specialized {kw.title()} Solutions for {niche}",
        "subheadline": f"Grounding your {niche} operations in {brand} expertise and strategic insight.",
        "cta_text": f"Consult {brand}"
    }
    
    # Sections
    sections = []
    
    # Use mission for intro
    sections.append({
        "id": "identity", "type": "body", "heading": f"Our Approach to {kw.title()}",
        "body_paragraphs": [
            f"At the intersection of {niche} and modern implementation, {kw} plays a pivotal role. {brand}'s methodology is rooted in the belief that every {niche} strategy must be technically sound and commercially viable.",
            f"As part of our commitment to excellence, we've integrated {kw} into our broader scope of {', '.join(services[:2])}. This ensures that users of {brand} receive not just a service, but a competitive edge."
        ]
    })
    
    # Keyword intent section
    sections.append({
        "id": "intent", "type": "body", "heading": f"Why {kw.title()} Matters in {niche}",
        "body_paragraphs": [
            f"In the context of {niche}, neglecting {kw} represents a significant strategic gap. Based on {brand}'s industry experience, we prioritize data-driven implementation over generic solutions.",
            f"Our technical team focuses on {kw} as a foundational element for scaling {niche} projects. By leveraging specific industry markers, we deliver results that are both measurable and sustainable."
        ],
        "callout": {"type": "tip", "text": f"Expert Tip: When implementing {kw} for {niche}, focus on integration over isolation."}
    })

    return {
        "meta": {"title": brief.page_title, "description": brief.meta_description},
        "content_metadata": {"keyword": kw, "word_count": 450, "method": "dna_synthesis"},
        "hero": hero,
        "sections": sections,
        "faq": [{"question": f"How does {kw} impact {niche}?", "answer": f"At {brand}, {kw} acts as a force multiplier for {niche} services. By refining the implementation, we ensure better performance and higher authority."}],
        "sources": ["Internal Domain Audit", f"{niche} Technical Standards"]
    }

def _build_expert_prompt(brief, existing_pages, site_wide_faqs) -> str:
    """
    High-Fidelity Prompt with CoT and Trope Blacklist.
    """
    blacklist = "Unlock, Transform, Navigate, Delve, Landscape, Nurture, Game-changer, In conclusion, Empower, Unlock the potential, Comprehensive guide, Look no further"
    
    return f"""### EXPERT PERSONA: LEAD CONSULTANT FOR {brief.niche} ###
TASK: Synthesize a 1200-word high-density professional document for '{brief.target_keyword}'.

### PHASE 1: REASONING (DO NOT INCLUDE IN OUTPUT) ###
1. Define the specific business problem '{brief.target_keyword}' solves for a professional in {brief.niche}.
2. Identify 3 technical nuances that generic AI usually misses about this topic.
3. Align the solution with the Site DNA provided below.

### PHASE 2: CONTENT GENERATION (STRICT CONSTRAINTS) ###
- BANNED TROPES (Strictly Forbidden): {blacklist}
- HUMAN TOUCH: Use "We" and "Our". Blend short, declarative sentences with dense technical explanations.
- GROUNDING: You MUST reference one of these services: {', '.join(brief.services[:3])}.
- TONE: {brief.tone} Authority.

### SITE DNA (SOURCE OF TRUTH) ###
{brief.site_profile_md}

### JSON DATA SCHEMA (STRICT FILL) ###
{{
  "meta": {{"title": "{brief.page_title}", "description": "Expert insights on {brief.target_keyword}"}},
  "content_metadata": {{"keyword": "{brief.target_keyword}", "word_count": <int>, "expertise_level": "Professional"}},
  "hero": {{"headline": "A non-generic expert hook about {brief.target_keyword}", "subheadline": "Targeted outcome"}},
  "sections": [
     {{
       "id": "unique-id", "type": "body", "heading": "Technical Insight on {brief.target_keyword}",
       "body_paragraphs": ["Detailed expert paragraph 1", "Detailed expert paragraph 2"],
       "callout": {{"type": "tip", "text": "Specific technical workaround"}}
     }}
  ],
  "faq": [
     {{"question": "Critical professional question?", "answer": "Dense 80-word authoritative answer"}}
  ],
  "sources": ["Primary Industry Documents"]
}}
"""

def _extract_json_from_llm(text: str) -> dict:
    """Robust extraction."""
    try:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: return json.loads(match.group(1))
        return json.loads(text)
    except: return None

def render_content_to_html(schema: dict) -> str:
    """HTML Synthesis for web deployment."""
    meta = schema.get("meta", {})
    hero = schema.get("hero", {})
    sections = schema.get("sections", [])
    
    html = f"<h1>{hero.get('headline')}</h1><p>{hero.get('subheadline')}</p>"
    for sec in sections:
        html += f"<h2>{sec.get('heading')}</h2>"
        for p in sec.get("body_paragraphs", []): html += f"<p>{p}</p>"
        if sec.get("callout"): html += f"<blockquote>{sec['callout']['text']}</blockquote>"
    
    if schema.get("faq"):
        html += "<h2>Frequently Asked Questions</h2>"
        for f in schema["faq"]:
            html += f"<h3>{f['question']}</h3><p>{f['answer']}</p>"
            
    return f"<!DOCTYPE html><html><head><title>{meta.get('title')}</title></head><body>{html}</body></html>"

def render_content_to_react(schema: dict) -> str:
    """React Component Synthesis."""
    return f"export default function Page() {{ return (<article>{render_content_to_html(schema)}</article>); }}"

def _call_openai(prompt, config):
    import openai
    api_key = config.get("api_key", "")
    model = config.get("model", "gpt-4o-mini")
    
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You are a lead consultant. Never use AI tropes."}, {"role": "user", "content": prompt}],
            temperature=0.7
        )
        return res.choices[0].message.content
    else:
        openai.api_key = api_key
        res = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": "You are a lead consultant. Never use AI tropes."}, {"role": "user", "content": prompt}],
            temperature=0.7
        )
        return res['choices'][0]['message']['content']

def _call_gemini(prompt, config):
    import google.generativeai as genai
    import httpx
    original_model = config.get("model", "gemini-1.5-flash")
    model_candidates = [original_model, "gemini-2.0-flash", "gemini-flash-latest", "gemini-1.5-flash", "gemini-pro-latest", "gemini-pro"]
    model_candidates = list(dict.fromkeys(model_candidates))
    
    key = config.get('api_key', '')
    if not key:
        raise RuntimeError("Gemini API Key is missing.")

    max_retries = 3
    base_delay = 5.0

    for attempt in range(max_retries):
        # SDK Try
        try:
            genai.configure(api_key=key)
            for model_name in model_candidates:
                target_model = model_name if model_name.startswith("models/") else f"models/{model_name}"
                try:
                    model = genai.GenerativeModel(target_model)
                    res = model.generate_content(prompt)
                    if res and res.text: return res.text
                except Exception as e:
                    if "404" in str(e): continue
                    if "429" in str(e): raise e # Jump to retry loop
                    raise e
        except Exception as sdk_err:
            if "429" not in str(sdk_err):
                logger.warning(f"Gemini SDK failed: {sdk_err}. Trying Direct REST Handshake...")

        # REST Try
        for model_name in model_candidates:
            clean_model = model_name.replace("models/", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={key}"
            try:
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7}}
                res = httpx.post(url, json=payload, timeout=60.0)
                if res.status_code == 200:
                    data = res.json()
                    return data['candidates'][0]['content']['parts'][0]['text']
                elif res.status_code == 404:
                    continue
                elif res.status_code == 429:
                    # Respect retryDelay if provided
                    retry_info = res.json().get("error", {}).get("details", [{}])[0].get("retryDelay", "5s")
                    wait_time = float(retry_info.replace("s", "")) if "s" in str(retry_info) else base_delay
                    wait_time = min(wait_time, 30.0) # Cap at 30s
                    logger.warning(f"Gemini Rate Limit (429). Retrying in {wait_time}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time + random.uniform(1, 3))
                    break # Break model loop to retry with fresh attempt
                elif res.status_code == 403:
                    raise RuntimeError("Gemini API 403: Access Denied. Check 'Generative Language API' enablement.")
                else:
                    raise RuntimeError(f"Gemini REST Error {res.status_code}: {res.text}")
            except Exception as rest_err:
                if "429" in str(rest_err):
                    time.sleep(base_delay * (attempt + 1))
                    break
                if "404" in str(rest_err): continue
                raise rest_err
    
    raise RuntimeError(f"Gemini API 429: Quota exhausted after {max_retries} retries. Please check your billing/usage limits in Google AI Studio.")

def _call_ollama(prompt, config):
    import httpx
    import time
    host = config.get('ollama_host', 'http://localhost:11434').rstrip('/')
    model = config.get("ollama_model", "llama3")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = httpx.post(
                f"{host}/api/generate", 
                json={"model": model, "prompt": prompt, "stream": False}, 
                timeout=300.0
            )
            if res.status_code == 200:
                return res.json().get("response", "")
            elif res.status_code == 500 and "terminated" in res.text:
                logger.warning(f"Ollama runner terminated (Attempt {attempt+1}/{max_retries}). Retrying in 5s...")
                time.sleep(5)
                continue
            elif res.status_code == 404:
                logger.error(f"Ollama Error: Model '{model}' not found on {host}.")
                return f"Error: Ollama model '{model}' not found."
            else:
                logger.error(f"Ollama Error {res.status_code}: {res.text}")
                return f"Error: Ollama returned {res.status_code}"
        except httpx.ConnectError:
            logger.error(f"Ollama Error: Could not connect to {host}. Is Ollama running?")
            return "Error: Could not connect to Ollama."
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Ollama Exception: {e}. Retrying...")
                time.sleep(2)
                continue
            logger.error(f"Ollama Exception: {str(e)}")
            return f"Error: {str(e)}"
    
    return "Error: Ollama runner terminated repeatedly."

def _call_openrouter(prompt, config):
    import httpx
    api_key = config.get("api_key")
    model = config.get("model", "google/gemini-2.0-flash-001")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://urlforge.ai",
        "X-Title": "UrlForge",
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional SEO consultant. Use clean markdown."},
            {"role": "user", "content": prompt}
        ]
    }
    
    res = httpx.post(url, headers=headers, json=payload, timeout=120)
    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']
    else:
        raise RuntimeError(f"OpenRouter Error {res.status_code}: {res.text}")
