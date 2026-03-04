# src/engine.py

from src.audit import generate_audit_report
from src.fixer import fix_urls
from src.modules.sitemap import fix_sitemap
from src.modules.canonical import fix_canonical_tags
from src.modules.robots import fix_robots
from src.modules.meta import analyze_meta, generate_meta_tags


def run_engine(pages, clean_urls, domain):
    audit = generate_audit_report(pages, clean_urls)

    plan = build_fix_plan(audit)

    # Analyze and generate meta fixes
    meta_issues = analyze_meta(pages)
    meta_fixes = generate_meta_tags(pages)

    context = {
        "urls": clean_urls,
        "domain": domain,
        "pages": pages,
        "meta_issues": meta_issues,
        "meta_fixes": meta_fixes
    }

    # Apply modular fixes
    if "sitemap" in plan:
        context["urls"] = fix_sitemap(context["urls"])

    if "canonical" in plan:
        context["urls"] = fix_canonical_tags(context)

    if "robots" in plan:
        fix_robots(context)

    # Generic URL fixes
    context["urls"] = fix_urls(context["urls"])

    return {
        "audit": audit,
        "plan": plan,
        "fixed_urls": context["urls"],
        "meta_issues": context["meta_issues"],
        "meta_fixes": context["meta_fixes"]
    }


def build_fix_plan(audit):
    plan = []

    if audit["issues"]["duplicates"]:
        plan.append("sitemap")

    if audit["issues"]["has_query_params"]:
        plan.append("sitemap")

    if audit["issues"]["not_https"]:
        plan.append("sitemap")

    # Future modules
    plan.append("canonical")
    plan.append("robots")

    return plan
