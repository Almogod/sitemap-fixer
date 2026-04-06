# src/modules/hardcode_fixer.py
"""
Hardcoded rule engine for site-wide consistency fixes.
Handles generic string/regex replacements to fix enterprise-level flaws
that aren't strictly SEO-tag related.
"""

import re
from src.utils.logger import logger

def run(context):
    """
    Detects potential hardcode flaws based on common patterns.
    Actually applying these requires user-defined rules, but we can detect 
    and propose 'fixes' for common issues here.
    """
    pages = context.get("pages", [])
    issues = []
    suggestions = {}

    # Example: Site-wide patterns to flag
    # In a real enterprise run, these would be loaded from config
    PATTERNS = [
        {"name": "placeholder_text", "regex": r"Lorem ipsum|\[Insert .*\]", "severity": "major"},
        {"name": "outdated_copyright", "regex": r"©\s*20\d{2}", "severity": "minor"},
        {"name": "inconsistent_branding", "regex": r"MyOldBrand", "severity": "major"}
    ]

    for page in pages:
        url = page.get("url")
        html = page.get("html", "")
        if not html: continue
        
        page_suggestions = []
        for p in PATTERNS:
            if re.search(p["regex"], html, re.IGNORECASE):
                issues.append({
                    "url": url,
                    "issue": p["name"],
                    "severity": p["severity"]
                })
                page_suggestions.append({
                    "type": "hardcode_fixation",
                    "pattern_name": p["name"],
                    "regex": p["regex"]
                })
        
        if page_suggestions:
            suggestions[url] = page_suggestions

    return {
        "issues": issues,
        "suggestions": suggestions
    }
