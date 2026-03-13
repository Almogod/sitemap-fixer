def build_fix_plan(audit):

    issues = audit.get("issues", {})

    plan = []

    if issues.get("duplicates"):
        plan.append("sitemap")

    if issues.get("has_query_params"):
        plan.append("sitemap")

    if issues.get("not_https"):
        plan.append("sitemap")

    if issues.get("missing_title") or issues.get("missing_description"):
        plan.append("meta")

    # internal linking should always run if graph exists
    plan.append("internal_links")
    plan.append("crawl_budget")
    plan.append("canonical")
    plan.append("robots")
    plan.append("schema")
    plan.append("image_seo")
    plan.append("core_web_vitals")
    plan.append("keyword_gap")

    return plan
