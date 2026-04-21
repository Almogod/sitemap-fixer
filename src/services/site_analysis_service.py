from src.content.page_generator import _call_openai, _call_gemini, _call_ollama
from src.config import config
from src.utils.logger import logger
import json

def synthesize_business_analysis(domain: str, structured_data: list, llm_config: dict = None) -> str:
    """
    Takes all structured chunks and synthesizes them into a final report.
    """
    logger.info(f"Synthesizing final business analysis for {domain}...")
    
    # Flatten the data for the LLM
    combined_context = json.dumps(structured_data, indent=2)
    
    prompt = f"""### FINAL BUSINESS ANALYSIS SYNTHESIS ###
Based on the following extracted data points from the homepage of {domain}, generate a comprehensive Professional Business Analysis Report.

EXTRACTED DATA:
{combined_context}

REPORT STRUCTURE:
1. Executive Summary
2. Core Service Offerings
3. Brand DNA & Mission
4. Target Audience Analysis
5. Technical Maturity & Stack
6. Competitive Advantages (Value Props)
7. Strategic Recommendations

Use professional, authoritative markdown.
"""

    if not llm_config:
        llm_config = {
            "provider": config.LLM_PROVIDER,
            "api_key": config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None,
            "gemini_key": config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None,
            "model": "gpt-4o-mini" if config.LLM_PROVIDER == "openai" else "gemini-1.5-flash"
        }
    
    provider = llm_config.get("provider", config.LLM_PROVIDER)
    api_key = llm_config.get("api_key")
    
    if not api_key:
        if provider == "openai":
            api_key = llm_config.get("openai_key") or (config.OPENAI_API_KEY.get_secret_value() if config.OPENAI_API_KEY else None)
        elif provider == "gemini":
            api_key = llm_config.get("gemini_key") or (config.GEMINI_API_KEY.get_secret_value() if config.GEMINI_API_KEY else None)
        elif provider == "ollama":
            api_key = "ollama"

    # Internal call expects "api_key"
    call_config = llm_config.copy()
    call_config["api_key"] = api_key

    try:
        report = ""
        if provider == "openai":
            report = _call_openai(prompt, call_config)
        elif provider == "gemini":
            report = _call_gemini(prompt, call_config)
        elif provider == "ollama":
            report = _call_ollama(prompt, call_config)
            
        return report
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return f"# Analysis Report for {domain}\n\nError generating full synthesis: {str(e)}"
