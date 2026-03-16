from bs4 import BeautifulSoup
from typing import Dict, Optional

def detect_framework(headers: Dict[str, str], html: str, url: str = "") -> str:
    """
    Detects the web framework and specific platform patterns.
    """
    server = headers.get("Server", "").lower()
    powered_by = headers.get("X-Powered-By", "").lower()
    
    # 1. Next.js & Vercel
    if "next.js" in powered_by or "vercel" in server:
        if "/api/revalidate" in html or "/api/revalidate" in url:
            return "next.js-isr"
        return "next.js"
        
    # 2. Astro
    if "astro" in html.lower() or "astro" in server:
        return "astro"
        
    # 3. Webflow
    if "webflow" in html.lower() or "webflow" in server:
        if "/detail_" in url or "/cms/" in url:
            return "webflow-cms"
        return "webflow"
        
    # 4. Framer
    if "framer" in html.lower() or "#" in url: # Framer often uses hash routing
        return "framer"

    soup = BeautifulSoup(html, "lxml")
    if soup.find("script", id="__NEXT_DATA__"):
        return "next.js"
    if soup.find("div", id="__nuxt"):
        return "nuxt.js"
    if soup.find("astro-island"):
        return "astro"
        
    return "unknown"

def is_vercel_preview(url: str) -> bool:
    """Detects if a URL is a Vercel preview deployment."""
    return ".vercel.app" in url and not url.endswith("vercel.app")

def get_auth_requirement(url: str) -> Optional[str]:
    """Determines if a URL requires special authentication (e.g., Vercel Preview)."""
    if is_vercel_preview(url):
        return "vercel-preview-token"
    return None
