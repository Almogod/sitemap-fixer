import httpx
import json
from src.utils.logger import logger
from src.content.page_generator import _call_openai, _call_gemini, _call_ollama, _extract_json_from_llm

def discover_competitors(domain: str, llm_config: dict = None) -> list:
    """
    Automatically identifies the site's niche and top category competitors using LLM insight.
    This corresponds to the 'Domain Identification' and 'Domain Search' nodes in the architecture.
    """
    logger.info(f"LLM-driven Domain Identification for {domain}...")
    
    if not llm_config or not (llm_config.get("api_key") or llm_config.get("provider") == "ollama"):
        logger.warning("No API key for competitor discovery. Using heuristics.")
        return _heuristic_competitors(domain)

    prompt = f"""You are a Strategic Market Analyst. 
Analyze the domain '{domain}' and identify its high-level industry niche and top 5 category competitors.

FOR SITE OPTIMIZATION: We need to know who is winning the search/answer engine space in this specific category.

STRICT JSON OUTPUT:
{{
  "niche": "string",
  "target_audience": "string",
  "competitors": ["domain1.com", "domain2.com", "domain3.com"]
}}
"""
    try:
        provider = llm_config.get("provider", "openai").lower()
        raw_res = None
        if provider == "openai": raw_res = _call_openai(prompt, llm_config)
        elif provider == "gemini": raw_res = _call_gemini(prompt, llm_config)
        elif provider == "ollama": raw_res = _call_ollama(prompt, llm_config)
        
        data = _extract_json_from_llm(raw_res)
        if data and "competitors" in data:
            logger.info(f"Discovered niche: {data.get('niche')} for {domain}")
            return data["competitors"]
    except Exception as e:
        logger.error(f"Competitor discovery failed: {e}")

    return _heuristic_competitors(domain)


def _heuristic_competitors(domain):
    """Fallback logic when API is unavailable."""
    niche_map = {
        "ecommerce": ["amazon.com", "ebay.com", "shopify.com"],
        "tech": ["theverge.com", "techcrunch.com", "wired.com"],
        "saas": ["hubspot.com", "salesforce.com", "intercom.com"],
        "news": ["cnn.com", "bbc.com", "nytimes.com"]
    }
    if "shop" in domain or "store" in domain: return niche_map["ecommerce"]
    if "tech" in domain or "dev" in domain: return niche_map["tech"]
    if "tool" in domain or "app" in domain: return niche_map["saas"]
    return ["competitor1.com", "competitor2.com"]


def get_competitor_pages(competitor_domains: list, limit_per_comp=5) -> list:
    """
    Simulates getting top pages from competitors for gap analysis.
    In a production enterprise crawler, this might trigger a lightweight crawl of these domains.
    """
    all_pages = []
    for comp in competitor_domains:
        # Simulated 'Top Pages' discovery
        all_pages.append({"url": f"https://{comp}/blog", "title": f"{comp} Blog"})
        all_pages.append({"url": f"https://{comp}/features", "title": f"{comp} Features"})
    return all_pages
