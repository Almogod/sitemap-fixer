def compute_score(engine_results):
    """
    Advanced Proportional SEO Scoring Engine.
    Deducts based on (Affected Pages / Total Pages) * Weight * Severity.
    """
    
    # Module weights (Total = 100)
    weights = {
        "meta": 15,
        "broken_links": 20,
        "mobile_seo": 10,
        "heading_structure": 10,
        "core_web_vitals": 10,
        "structured_data_validator": 10,
        "image_seo": 5,
        "open_graph": 5,
        "page_speed": 5,
        "hreflang": 5,
        "content_quality": 5
    }

    # Default severities for legacy modules or unspecified issues
    SEVERITY_MAP = {
        "critical": 1.0,
        "major": 0.7,
        "minor": 0.3
    }
    
    total_scanned = len(engine_results.get("pages", []))
    if total_scanned == 0:
        return 0

    total_deduction = 0
    modules = engine_results.get("modules", {})

    for module_name, weight in weights.items():
        result = modules.get(module_name)
        if not result:
            continue
            
        module_issues = result.get("issues", [])
        if not module_issues:
            # Bonus for perfectly clean modules
            continue
            
        module_deduction = 0
        
        # Handle both legacy dict-of-lists and new enriched issue format
        if isinstance(module_issues, dict):
            # Legacy format: {"issue_type": [url1, url2...]}
            for issue_type, urls in module_issues.items():
                if not urls: continue
                
                # Assume major severity for legacy issues
                severity = 0.7 
                if any(k in issue_type for k in ["missing", "broken", "critical", "error"]):
                    severity = 1.0
                
                affected_pct = len(set(urls)) / total_scanned
                module_deduction += (affected_pct * weight * severity)
        
        elif isinstance(module_issues, list):
            # New format or site-wide list format
            for issue in module_issues:
                if not isinstance(issue, dict): continue
                
                severity = SEVERITY_MAP.get(issue.get("severity", "major").lower(), 0.7)
                
                # If 'pages' exists, use proportional deduction
                if "pages" in issue:
                    affected_pages = len(set(issue.get("pages", [])))
                    if affected_pages == 0: continue
                    affected_pct = affected_pages / total_scanned
                else:
                    # Site-wide issue (e.g. robots.txt missing) affects 100% impact
                    affected_pct = 1.0
                
                module_deduction += (affected_pct * weight * severity)

        # Cap module deduction at its total weight
        total_deduction += min(weight, module_deduction)

    # Calculate final score
    base_score = 100 - total_deduction
    
    # Audit baseline integration (70/30 split)
    # The audit baseline often catches high-level architectural issues
    audit_baseline = engine_results.get("audit", {}).get("score", 100)
    
    final_score = int((base_score * 0.7) + (audit_baseline * 0.3))
    
    return max(0, min(100, final_score))
