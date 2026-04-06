# src/content/engine.py
"""
The Content Generation Engine (REWRITTEN).
Orchestrates High-Fidelity Keyword Discovery and Strategic DNA Extraction.
Elimates generic filler through strict site-fragment analysis.
"""

from src.content.competitor_analyzer import analyze_competitors
from src.content.page_generator import generate_page
from src.content.stopwords import STOPWORDS
from src.utils.logger import logger
import re
import math
from collections import Counter
from bs4 import BeautifulSoup

def run_content_engine(site_pages, competitor_urls, llm_config, limit=3, domain=None):
    """
    High-Fidelity content-gap pipeline.
    """
    logger.info("UrlForge Engine: Starting Strategic Content Discovery")
    
    # 1. Advanced DNA Clustering
    site_keywords = _extract_bulk_keywords(site_pages)
    site_bigrams = _extract_bulk_bigrams(site_pages)
    
    # Ranked weighted terms
    prime_keywords = [kw for kw, _ in site_keywords.most_common(12)]
    
    # 2. Competitor Gap Analysis
    gaps = {}
    all_site_terms = set(site_keywords.keys()) | set(site_bigrams.keys())
    
    if competitor_urls:
        for comp_url in competitor_urls[:5]:
            try:
                from src.content.competitor_analyzer import _fetch_page, _tokenize, _extract_ngrams
                page_html = _fetch_page(comp_url)
                if page_html:
                    soup = BeautifulSoup(page_html, "lxml")
                    text = soup.get_text(" ", strip=True)
                    tokens = _tokenize(text)
                    comp_terms = set(tokens) | set(_extract_ngrams(tokens, 2))
                    
                    gap_terms = [t for t in comp_terms if t not in all_site_terms and len(t) > 5]
                    if gap_terms:
                        gaps[comp_url] = sorted(gap_terms, key=len, reverse=True)[:10]
            except Exception as e:
                logger.warning(f"Gap Analysis failed for {comp_url}: {e}")
                
    return {
        "keyword_gap": gaps,
        "site_keywords": [kw for kw, _ in site_keywords.most_common(40)],
        "site_bigrams": [bg for bg, _ in site_bigrams.most_common(30)],
        "prime_keywords": prime_keywords,
        "recommendations": [{"keyword": kw, "source": url} for url, kws in gaps.items() for kw in kws[:3]]
    }

def is_noise(word: str) -> bool:
    """Returns True if the word looks like random gibberish or noise."""
    if len(word) < 5: return True
    if not any(v in word for v in "aeiouy"): return True # No vowels
    # Basic entropy check: low vowel ratio (less than 15%)
    vowels = sum(1 for c in word if c in "aeiouy")
    if vowels / len(word) < 0.15: return True
    # Too many repeated characters (e.g., "aaaaa")
    if any(word.count(c) > len(word) / 2 for c in set(word)): return True
    return False

def _extract_bulk_keywords(pages) -> Counter:
    """TF-IDF adjacent weighted keyword extraction with Noise Filter."""
    counts = Counter()
    total_pages = len(pages)
    if total_pages == 0: return counts
    
    processed_pages = []
    df = Counter()
    for p in pages:
        html = p.get("html", "")
        body_text = ""
        if html:
            soup = BeautifulSoup(html, "lxml")
            # Decompose common noise containers
            for s in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]): 
                s.decompose()
            body_text = soup.get_text(" ", strip=True)[:3000]
            
        title = p.get('title', '')
        meta_desc = p.get('meta_description', '')
        combined_text = f"{title} {meta_desc} {body_text}".lower()
        # Find all alpha strings
        raw_words = re.findall(r'\b[a-z]{4,}\b', combined_text)
        words = [w for w in raw_words if w not in STOPWORDS and not is_noise(w)]
        
        unique_words = set(words)
        for w in unique_words:
            df[w] += 1
            
        processed_pages.append({
            "words": words,
            "title_lower": title.lower()
        })
            
    # Term frequency * IDF
    for p in processed_pages:
        words = p["words"]
        title_lower = p["title_lower"]
        for w in words:
            idf = math.log(total_pages / (1 + df[w]))
            # Weight Title words higher
            weight = 3.0 if w in title_lower else 1.0
            counts[w] += (weight * idf)
            
    return counts

def _extract_bulk_bigrams(pages) -> Counter:
    """High-signal phrase extraction with Noise Filter."""
    bigrams = Counter()
    for p in pages:
        text = f"{p.get('title', '')} {p.get('meta_description', '')}".lower()
        words = [w for w in re.findall(r'\b[a-z]{4,}\b', text) if w not in STOPWORDS and not is_noise(w)]
        for i in range(len(words) - 1):
            bigrams[f"{words[i]} {words[i+1]}"] += 1
    return bigrams

def _find_strategic_pages(pages):
    """Hunt for the Site DNA (About/Services/Home)."""
    strategic = []
    patterns = [
        r"/(about|who-we-are|mission|story|team)",
        r"/(services|solutions|what-we-do|products|capabilities|expertise)",
        r"/$"
    ]
    for pattern in patterns:
        for p in pages:
            if re.search(pattern, p.get("url", "").lower()) and p not in strategic:
                strategic.append(p)
                if len(strategic) >= 5: return strategic
    return strategic or pages[:3]

def _generate_heuristic_profile(pages, domain):
    """Zero-Generic heuristic profiling."""
    keywords = _extract_bulk_keywords(pages)
    
    # Be more selective about the niche
    top_terms = [k.title() for k, _ in keywords.most_common(12) if len(k) > 3]
    
    # Domain-Signaling Fallback: If no keywords, split the domain
    if not top_terms and domain:
        clean_domain = domain.split('.')[1] if '.' in domain else domain
        # Split camelCase or hyphens
        parts = re.findall(r'[a-zA-Z][a-z]*', clean_domain)
        top_terms = [p.title() for p in parts if len(p) > 2]
        
    niche = " / ".join(top_terms[:3]) if top_terms else "Digital Engineering"
    
    metas = [p.get("meta_description", "") for p in pages if p.get("meta_description")]
    mission = max(metas, key=len) if metas else f"Technical authority specializing in {niche} solutions with a focus on high-fidelity implementation."
    
    return {
        "domain": domain, 
        "niche": niche, 
        "mission": mission,
        "primary_purpose": f"Advanced {niche} operations and strategy for industrial clients.",
        "tone": "Authoritative",
        "topics": [k.lower() for k, _ in keywords.most_common(20)] if keywords else top_terms,
        "services": [f"{t} Implementation" for t in top_terms[:4]]
    }

def analyze_site_content(pages, domain, llm_config=None):
    """
    Strategic Site Analysis (Deep DNA).
    No API? Refuses to guess 'General' if keyword signals are strong.
    """
    from src.content.page_generator import _call_openai, _call_gemini, _call_ollama, _extract_json_from_llm
    
    if not pages:
        return {"domain": domain, "niche": "None", "error": "No pages detected"}

    strat_pages = _find_strategic_pages(pages)
    dna_blocks = []
    for p in strat_pages:
        html = p.get("html", "")
        if html:
            soup = BeautifulSoup(html, "lxml")
            for s in soup(["script", "style", "nav", "footer"]): s.decompose()
            text = soup.get_text(" ", strip=True)[:2500]
            dna_blocks.append(f"URL: {p.get('url')}\nCONTENT:\n{text}")
            
    combined_dna = "\n\n---\n\n".join(dna_blocks)
    
    # API Sanity Check: Skip placeholders/defaults
    api_key = llm_config.get("api_key", "")
    is_placeholder = "your_sk" in api_key or "placeholder" in api_key or len(api_key) < 15
    has_api = llm_config and not is_placeholder and (bool(api_key) or llm_config.get("provider") == "ollama")

    if has_api:
        logger.info(f"LLM DNA Audit for {domain}...")
        prompt = f"""AUDIT TASK: Define 100% accurate Brand DNA for {domain}.
DEEP DNA SAMPLES FROM SITE:
{combined_dna}

STRICT JSON OUTPUT:
{{
  "niche": "industrial specific niche",
  "mission": "unique value proposition",
  "tone": "authoritative|educational|persuasive",
  "tone_markers": ["marker1", "marker2"],
  "services": ["service: description"],
  "pain_points": ["problem solved"],
  "primary_purpose": "short summary"
}}
"""
        try:
            provider = llm_config.get("provider", "openai").lower()
            res = None
            if provider == "openai": res = _call_openai(prompt, llm_config)
            elif provider == "gemini": res = _call_gemini(prompt, llm_config)
            elif provider == "ollama": res = _call_ollama(prompt, llm_config)
            
            data = _extract_json_from_llm(res)
            if data and "niche" in data:
                data["discovery_method"] = "high_fidelity_api"
                data["domain"] = domain
                data["sample_titles"] = [p.get("title", "") for p in pages[:10]]
                return data
        except Exception as e:
            logger.error(f"DNA API failed: {e}")

    # Heuristic Fallback
    logger.info(f"Fallback: Building Strategic Profile from clustering for {domain}")
    profile = _generate_heuristic_profile(pages, domain)
    profile["discovery_method"] = "high_fidelity_heuristic"
    profile["sample_titles"] = [p.get("title", "") for p in pages[:10]]
    return profile

def generate_markdown_site_profile(domain_context):
    """
    Converts domain_context into a formatted Markdown Strategic DNA Report.
    """
    domain = domain_context.get("domain", "Unknown Site")
    niche = domain_context.get("niche", "General")
    tone = domain_context.get("tone", "Conversational")
    mission = domain_context.get("mission", "None detected.")
    purpose = domain_context.get("primary_purpose", "Business operations.")
    services = domain_context.get("services", [])
    
    md = f"# 🕵️ Strategic DNA Report: {domain}\n\n"
    
    md += f"## 🎯 Strategic Identity\n"
    md += f"- **Niche:** {niche}\n"
    md += f"- **Primary Purpose:** {purpose}\n"
    md += f"- **Brand Persona:** {tone.title()}\n"
    md += f"- **Mission:** {mission}\n\n"

    md += f"## 🛠️ Core Capabilities\n"
    if services:
        for s in services:
            name = s.get('name', s) if isinstance(s, dict) else s
            desc = s.get('detailed_description', '') if isinstance(s, dict) else ""
            md += f"- **{name}**: {desc}\n"
    else:
        md += f"- Authority in the {niche} sector.\n"

    md += "\n---\n"
    md += "*This business audit was automatically generated via UrlForge DNA Discovery (Site Fragments).* "
    return md

def verify_keyword_relevance(keyword, domain_context):
    """
    Verify that a keyword is actually relevant to the site's content.
    """
    kw = keyword.lower()
    niche = domain_context.get("niche", "").lower()
    mission = domain_context.get("mission", "").lower()
    topics = " ".join(domain_context.get("topics", [])).lower()
    titles = " ".join(domain_context.get("sample_titles", [])).lower()
    
    search_space = f"{niche} {mission} {topics} {titles}"
    
    # Check if any part of the keyword is in the search space
    kw_words = kw.split()
    relevance_score = sum(1 for w in kw_words if w in search_space and len(w) > 3)
    
    return relevance_score > 0 or len(kw_words) > 3

def generate_content_for_keyword(keyword, competitor_urls, llm_config, existing_pages=None, domain_context=None, site_wide_faqs=None):
    """
    Targeted high-fidelity generation.
    """
    try:
        logger.info(f"Generating content for keyword: {keyword}")
        domain_context = domain_context or {}
        
        # 1. Build Brief
        brief = analyze_competitors(
            competitor_urls=competitor_urls or [], 
            target_keyword=keyword, 
            domain=domain_context.get("domain", ""),
            site_profile_md=generate_markdown_site_profile(domain_context),
            niche=domain_context.get("niche", "General")
        )
        
        # Inject domain markers
        brief.tone = domain_context.get("tone", brief.tone)
        brief.services = domain_context.get("services", [])
        brief.pain_points = domain_context.get("pain_points", [])
        brief.tone_markers = domain_context.get("tone_markers", [])

        # 2. Generate
        result = generate_page(brief, llm_config, existing_pages, site_wide_faqs)
        
        # 3. Finalize
        from src.content.page_generator import render_content_to_html, render_content_to_react
        result["html"] = render_content_to_html(result.get("schema_data", {}))
        result["react_jsx"] = render_content_to_react(result.get("schema_data", {}))
        
        return result
    except Exception as e:
        logger.error(f"Failed to generate content for {keyword}: {e}", exc_info=True)
        return {"error": str(e)}
