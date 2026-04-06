# src/modules/meta.py

from bs4 import BeautifulSoup


def run(context):
    """
    Standard module interface.
    Receives context from engine and returns structured result.
    """

    pages = context["pages"]

    # Standardized enriched issue format
    enriched_issues = [
        {"type": "missing_title", "severity": "critical", "pages": []},
        {"type": "missing_description", "severity": "major", "pages": []},
        {"type": "missing_h1", "severity": "major", "pages": []},
        {"type": "multiple_h1", "severity": "minor", "pages": []}
    ]

    # Helper to find issue in list
    def get_issue(issue_type):
        for i in enriched_issues:
            if i["type"] == issue_type: return i
        return None

    fixes = {}

    for page in pages:
        html = page.get("html")
        url = page.get("url")
        if not html: continue

        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        desc_tag = soup.find("meta", attrs={"name": "description"})
        h1_tags = soup.find_all("h1")

        if not title_tag or not title_tag.text.strip():
            get_issue("missing_title")["pages"].append(url)
            title = _api_generate_title(url, soup, context)
        else:
            title = title_tag.text.strip()

        if not desc_tag or not desc_tag.get("content"):
            get_issue("missing_description")["pages"].append(url)
            description = _api_generate_description(url, soup, context)
        else:
            description = desc_tag.get("content")

        if not h1_tags:
            get_issue("missing_h1")["pages"].append(url)

        if len(h1_tags) > 1:
            get_issue("multiple_h1")["pages"].append(url)

        fixes[url] = {
            "title": title[:60],
            "description": description[:155]
        }

    return {
        "issues": enriched_issues,
        "fixes": fixes
    }


# ------------------------------------
# API GENERATORS
# ------------------------------------
def _api_generate_title(url, soup, context):
    from src.content.page_generator import _call_openai, _call_gemini, _call_ollama, _extract_json_from_llm
    
    llm_config = context.get("llm_config")
    if not llm_config or not (llm_config.get("api_key") or llm_config.get("provider") == "ollama"):
        return _fallback_title(url, soup)

    h1 = soup.find("h1")
    h1_text = h1.text.strip() if h1 else "Unknown"
    
    prompt = f"Generate a high-click-through SEO title (max 60 chars) for this page. URL: {url}, H1: {h1_text}. Niche: {context.get('niche', 'General')}. Tone: {context.get('tone', 'professional')}. Return ONLY the title string."
    
    try:
        provider = llm_config.get("provider", "openai").lower()
        if provider == "openai": return _call_openai(prompt, llm_config).strip().strip('"')
        elif provider == "gemini": return _call_gemini(prompt, llm_config).strip().strip('"')
        elif provider == "ollama": return _call_ollama(prompt, llm_config).strip().strip('"')
    except: pass
    return _fallback_title(url, soup)

def _api_generate_description(url, soup, context):
    from src.content.page_generator import _call_openai, _call_gemini, _call_ollama
    
    llm_config = context.get("llm_config")
    if not llm_config or not (llm_config.get("api_key") or llm_config.get("provider") == "ollama"):
        return _fallback_description(soup)

    text = soup.get_text()[:1000]
    prompt = f"Generate a compelling SEO meta description (max 155 chars) for this page content. Content Sample: {text}. Niche: {context.get('niche', 'General')}. Tone: {context.get('tone', 'professional')}. Matches category competitors. Return ONLY the description string."
    
    try:
        provider = llm_config.get("provider", "openai").lower()
        if provider == "openai": return _call_openai(prompt, llm_config).strip().strip('"')
        elif provider == "gemini": return _call_gemini(prompt, llm_config).strip().strip('"')
        elif provider == "ollama": return _call_ollama(prompt, llm_config).strip().strip('"')
    except: pass
    return _fallback_description(soup)

def _fallback_title(url, soup):
    h1 = soup.find("h1")
    if h1 and h1.text.strip(): return h1.text.strip()
    slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
    return slug if slug else "Untitled Page"

def _fallback_description(soup):
    p = soup.find("p")
    return p.text.strip()[:155] if p else "Learn more about our site's mission and expertise."
