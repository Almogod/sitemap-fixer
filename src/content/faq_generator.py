# src/content/faq_generator.py
"""
Expert FAQ Generator (REWRITTEN).
Eliminates generic templates. Uses Site Fragment Synthesis for fallback.
"""

import re
import json
from collections import Counter
from bs4 import BeautifulSoup
from src.utils.logger import logger
from src.content.content_schema import FAQItem

def generate_site_faqs(site_keywords, domain, llm_config, site_context=None):
    """
    Expert FAQ pipeline: API-First, Fragment-Synthesis Fallback.
    """
    logger.info(f"FaqEngine: Synthesizing expert Q&A for {domain}")
    site_context = site_context or {}
    
    faqs = []
    has_api = bool(llm_config.get("api_key")) or llm_config.get("provider") == "ollama"

    if has_api:
        faqs = _generate_faqs_with_llm(site_keywords, domain, llm_config, site_context)
    
    if not faqs:
        logger.info(f"FaqEngine: API unavailable or failed. Using Fragment Synthesis for {domain}")
        faqs = _synthesize_faqs_from_fragments(site_keywords, domain, site_context)

    # Validate
    robust_faqs = []
    for item in faqs[:8]:
        q, a = item.get("question", ""), item.get("answer", "")
        if len(q) > 15 and len(a) > 30:
            robust_faqs.append(FAQItem(question=q, answer=a))
            
    return robust_faqs

def _generate_faqs_with_llm(keywords, domain, llm_config, site_context):
    """High-Fidelity Expert LLM FAQ Generation."""
    from src.content.page_generator import _call_openai, _call_gemini, _call_ollama, _extract_json_from_llm
    
    niche = site_context.get("niche", "Professional Services")
    mission = site_context.get("mission", "")
    
    prompt = f"""ROLE: You are the Lead Consultant at {domain} ({niche}).
TASK: Generate 7 Expert-Level FAQs that prove deep industry authority.

SITE MISSION: {mission}
TOPICS: {', '.join(keywords[:8])}

STRICT CONSTRAINTS:
1. NO AI-ISMS: Forbidden terms include 'Unlock', 'Transform', 'Navigate', 'Delve', 'Landscape'.
2. NO BASIC DEFINITIONS: Do not explain what a keyword is. Explain HOW {domain} implements it.
3. DATA-DRIVEN: Use phrases like "Based on our fieldwork," "Historically, we've found," "Our methodology prioritizes."
4. UNIQUE BRANDING: Every answer must reference a specific service or value from {domain}.

OUTPUT: Strict JSON Array of {{"question": "", "answer": ""}}
每一条 answer 必须在 60-100 字之间。
"""
    try:
        provider = llm_config.get("provider", "openai").lower()
        res = None
        if provider == "openai": res = _call_openai(prompt, llm_config)
        elif provider == "gemini": res = _call_gemini(prompt, llm_config)
        elif provider == "ollama": res = _call_ollama(prompt, llm_config)
        
        data = _extract_json_from_llm(res)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"FAQ LLM failed: {e}")
        return []

def _synthesize_faqs_from_fragments(keywords, domain, site_context):
    """
    Zero-Boilerplate Fallback. 
    Builds FAQs by pairing top keywords with actual descriptive mission/service text.
    """
    faqs = []
    mission = site_context.get("mission", "")
    services = site_context.get("services", [])
    niche = site_context.get("niche", "Expert Industry")
    
    # ── Strategy 1: Service-Based Q&A (High Fidelity) ─────────────
    for s in services[:4]:
        name = s.get("name") if isinstance(s, dict) else s
        desc = s.get("detailed_description") if isinstance(s, dict) else ""
        if not desc and mission: desc = mission
        
        faqs.append({
            "question": f"How does {domain} specialize in {name}?",
            "answer": f"{domain} provides targeted solutions for {name} within the {niche} sector. {desc} Our approach ensures that every {name} project meets specific industry standards while prioritizing client ROI."
        })
        
    # ── Strategy 2: Keyword-Mission Pairing ───────────────────────
    for kw in keywords[:3]:
        if len(faqs) >= 7: break
        faqs.append({
            "question": f"What is the {domain} approach to {kw.title()}?",
            "answer": f"At {domain}, {kw.title()} is integrated into our core mission of {mission}. We treat {kw} not just as a service, but as a strategic asset for our clients in the {niche} space."
        })
        
    return faqs
