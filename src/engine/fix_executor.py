# src/engine/fix_executor.py
"""
Translates module results into concrete fix actions that the html_rewriter can execute.
Covers all modules: meta, schema, image_seo, open_graph, canonical_advanced,
heading_structure, core_web_vitals, page_experience, mobile_seo,
broken_links, structured_data_validator.
"""


def execute_fixes(context, module_results, strategy):
    actions = []

    handler_map = {
        "meta":                     apply_meta_fixes,
        "schema":                   apply_schema_fixes,
        "image_seo":                apply_image_fixes,
        "open_graph":               apply_open_graph_fixes,
        "canonical_advanced":       apply_canonical_fixes,
        "heading_structure":        apply_heading_fixes,
        "core_web_vitals":          apply_cwv_fixes,
        "page_experience":          apply_page_experience_fixes,
        "mobile_seo":               apply_mobile_fixes,
        "page_speed":               apply_page_speed_fixes,
        "structured_data_validator": apply_structured_data_fixes,
        "hreflang":                 apply_hreflang_fixes,
        "broken_links":             apply_broken_link_fixes,
        "content_quality":          apply_content_quality_fixes,
        "hardcode_fixer":           apply_hardcode_fixes,
    }

    for module_name in strategy:
        result = module_results.get(module_name)
        if not result:
            continue
        handler = handler_map.get(module_name)
        if handler:
            try:
                actions += handler(result)
            except Exception:
                pass

    return actions


# ─────────────────────────────────────
# META
# ─────────────────────────────────────
def apply_meta_fixes(result):
    fixes = result.get("fixes", {})
    return [
        {
            "type": "update_meta",
            "url": url,
            "title": data.get("title"),
            "description": data.get("description")
        }
        for url, data in fixes.items()
    ]


# ─────────────────────────────────────
# SCHEMA (basic)
# ─────────────────────────────────────
def apply_schema_fixes(result):
    schemas = result.get("schemas", {})
    return [
        {"type": "inject_schema", "url": url, "schema": schema}
        for url, schema in schemas.items()
    ]


# ─────────────────────────────────────
# IMAGE SEO
# ─────────────────────────────────────
def apply_image_fixes(result):
    fixes = result.get("fixes", {})
    actions = []
    for url, page_fixes in fixes.items():
        for fix in page_fixes:
            actions.append({
                "type": fix.get("fix"),       # add_alt, rename_image, add_lazy_loading
                "url": url,
                "image": fix.get("image"),
                "value": fix.get("value")
            })
    return actions


# ─────────────────────────────────────
# OPEN GRAPH
# ─────────────────────────────────────
def apply_open_graph_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            actions.append({
                "type": "inject_into_head",
                "url": url,
                "tag": s.get("tag")
            })
    return actions


# ─────────────────────────────────────
# CANONICAL ADVANCED
# ─────────────────────────────────────
def apply_canonical_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t in ("add_canonical", "fix_canonical"):
                actions.append({
                    "type": t,
                    "url": url,
                    "tag": s.get("tag")
                })
    return actions


# ─────────────────────────────────────
# HEADING STRUCTURE
# ─────────────────────────────────────
def apply_heading_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            if s.get("type") == "fix_multiple_h1":
                actions.append({
                    "type": "demote_extra_h1",
                    "url": url
                })
            else:
                actions.append({
                    "type": "heading_fix",
                    "url": url,
                    "fix_type": s.get("type"),
                    "action": s.get("action")
                })
    return actions


# ─────────────────────────────────────
# HARDCODE FIXER
# ─────────────────────────────────────
def apply_hardcode_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            if s.get("type") == "hardcode_fixation":
                actions.append({
                    "type": "generic_replace",
                    "url": url,
                    "pattern": s.get("regex"),
                    "replacement": "FIXED_VALUE", # Generic placeholder for now
                    "is_regex": True
                })
    return actions


# ─────────────────────────────────────
# CORE WEB VITALS
# ─────────────────────────────────────
def apply_cwv_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            fix_type = s.get("type")
            if fix_type == "defer_script":
                actions.append({
                    "type": "defer_script",
                    "url": url,
                    "script": s.get("script")
                })
            elif fix_type == "add_image_dimensions":
                actions.append({
                    "type": "add_image_dimensions",
                    "url": url,
                    "image": s.get("image")
                })
    return actions


# ─────────────────────────────────────
# PAGE EXPERIENCE
# ─────────────────────────────────────
def apply_page_experience_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t == "fix_insecure_links":
                actions.append({"type": "fix_insecure_links", "url": url})
            elif t == "fix_mixed_content":
                actions.append({"type": "fix_mixed_content", "url": url})
    return actions


# ─────────────────────────────────────
# MOBILE SEO
# ─────────────────────────────────────
def apply_mobile_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t in ("add_viewport", "fix_viewport"):
                actions.append({
                    "type": t,
                    "url": url,
                    "tag": s.get("tag")
                })
    return actions


# ─────────────────────────────────────
# PAGE SPEED
# ─────────────────────────────────────
def apply_page_speed_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t in ("add_preload", "add_dns_prefetch", "add_charset"):
                actions.append({
                    "type": "inject_into_head",
                    "url": url,
                    "tag": s.get("tag")
                })
    return actions


# ─────────────────────────────────────
# STRUCTURED DATA
# ─────────────────────────────────────
def apply_structured_data_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t in ("inject_faq_schema", "inject_breadcrumb_schema"):
                actions.append({
                    "type": t,
                    "url": url,
                    "schema": s.get("schema")
                })
    return actions


# ─────────────────────────────────────
# HREFLANG
# ─────────────────────────────────────
def apply_hreflang_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            if s.get("type") == "add_hreflang":
                for tag_str in s.get("tags", []):
                    actions.append({
                        "type": "inject_into_head",
                        "url": url,
                        "tag": tag_str
                    })
    return actions


# ─────────────────────────────────────
# BROKEN LINKS
# ─────────────────────────────────────
def apply_broken_link_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            actions.append({
                "type": "broken_link_report",
                "url": url,
                "link": s.get("link"),
                "action": s.get("action")
            })
    return actions


# ─────────────────────────────────────
# CONTENT QUALITY
# ─────────────────────────────────────
def apply_content_quality_fixes(result):
    suggestions = result.get("suggestions", {})
    actions = []
    for url, page_suggestions in suggestions.items():
        for s in page_suggestions:
            t = s.get("type")
            if t == "expand_content":
                actions.append({
                    "type": "expand_content",
                    "url": url,
                    "current_words": s.get("current_words"),
                    "target_words": s.get("target_words")
                })
    return actions
