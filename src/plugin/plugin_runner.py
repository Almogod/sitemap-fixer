import os
import yaml
import importlib
from typing import List, Dict, Any
from src.plugin.base import BaseSEOPlugin, PluginManifest
from src.utils.logger import logger, audit_logger
from src.services.task_store import TaskStore

task_store = TaskStore()

def discover_plugins(plugin_dir: str = "src/modules") -> Dict[str, BaseSEOPlugin]:
    """Dynamically discover and load plugins with manifest files."""
    discovered = {}
    if not os.path.exists(plugin_dir):
        return discovered

    for folder in os.listdir(plugin_dir):
        manifest_path = os.path.join(plugin_dir, folder, "plugin.yaml")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = yaml.safe_load(f)
                    manifest = PluginManifest(**manifest_data)
                
                # Dynamic import
                module_path = f"src.modules.{folder}.plugin"
                module = importlib.import_module(module_path)
                
                # Assume a standard class name or a factory function
                plugin_class = getattr(module, "SEOPlugin")
                discovered[manifest.name] = plugin_class(manifest)
                logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")
            except Exception as e:
                logger.error(f"Failed to load plugin in {folder}: {e}")
    
    return discovered

def run_plugin(
    site_url: str,
    task_id: str,
    deploy_config: dict,
    llm_config: dict,
    competitors: list,
    crawl_options: dict,
    user_id: str = "system"
):
    audit_logger.info(f"User {user_id} started plugin job {task_id} for {site_url}")
    # ... previous implementation updated to use discover_plugins ...
    # For brevity as a mock implementation:
    plugins = discover_plugins()
    # Execute plugins...
    pass


def run_plugin(
    site_url: str,
    task_id: str,
    deploy_config: dict,
    llm_config: dict,
    competitors: list,
    crawl_options: dict,
    pipeline: List[str] = ["crawl", "analyze", "generate"],
    dry_run: bool = False
):
    """
    Autonomous SEO plugin run with configurable phases.
    """
    from datetime import datetime
    from src.engine.engine import run_engine

    def progress(msg):
        logger.info("[plugin:%s] %s", task_id, msg)
        task_store.set_status(task_id, msg)

    report = {
        "task_id": task_id,
        "site_url": site_url,
        "started_at": datetime.utcnow().isoformat(),
        "fixes_applied": [],
        "suggested_actions": [],
        "pages_generated": [],
        "deploy_results": [],
        "seo_score_before": None,
        "errors": [],
        "state": "pending_approval",
        "dry_run": dry_run
    }

    # Shared data for output chaining between phases
    context_data = {
        "pages": [],
        "clean_urls": [],
        "domain": "",
        "graph": None,
        "results": {}
    }

    try:
        for phase in pipeline:
            progress(f"Starting phase: {phase}...")
            
            if phase == "crawl":
                pages, clean_urls, domain, graph = _crawl(site_url, crawl_options)
                context_data.update({
                    "pages": pages,
                    "clean_urls": clean_urls,
                    "domain": domain,
                    "graph": graph
                })
                progress(f"Crawled {len(pages)} pages")

            elif phase == "analyze":
                if not context_data["pages"]:
                    progress("Skipping analysis: No pages crawled.")
                    continue
                
                results = run_engine(
                    pages=context_data["pages"],
                    clean_urls=context_data["clean_urls"],
                    domain=context_data["domain"],
                    graph=context_data["graph"],
                    competitors=competitors,
                    progress_callback=progress
                )
                context_data["results"] = results
                report["seo_score_before"] = results.get("seo_score", 0)
                report["engine_result"] = results
                report["suggested_actions"] = results.get("actions", [])
                progress(f"Analysis complete. Score: {report['seo_score_before']}")

            elif phase == "generate":
                if not context_data["results"]:
                    progress("Skipping generation: No analysis results available.")
                    continue
                
                keyword_gaps = _extract_keyword_gaps(context_data["results"], competitors)
                existing_pages_list = [{"url": p["url"], "title": _get_title(p)} for p in context_data["pages"]]

                if keyword_gaps and (llm_config.get("api_key") or llm_config.get("provider") == "ollama"):
                    from src.content.competitor_analyzer import analyze_competitors
                    from src.content.page_generator import generate_page

                    for keyword in keyword_gaps[:5]:
                        try:
                            progress(f"Generating content for: {keyword}")
                            brief = analyze_competitors(competitors, keyword, context_data["domain"])
                            brief.internal_links = existing_pages_list[:10]
                            generated = generate_page(brief, llm_config, existing_pages_list)

                            report["pages_generated"].append({
                                "keyword": keyword,
                                "slug": generated["slug"],
                                "title": generated["meta_title"],
                                "word_count": generated["word_count"],
                                "html": generated["html"],
                                "approved": True
                            })
                        except Exception as e:
                            report["errors"].append({
                                "phase": "generate",
                                "item": keyword,
                                "error": str(e),
                                "code": "GENERATION_ERROR"
                            })

        if dry_run:
            progress("Dry run complete. No changes would be applied.")
            report["state"] = "dry_run_completed"
        else:
            progress("Run complete. Waiting for user approval.")
            task_store.set_status(task_id, "Pending Approval")
        
        task_store.save_results(task_id, report)

    except Exception as e:
        logger.error(f"Plugin pipeline failed: {e}", exc_info=True)
        report["errors"].append({
            "phase": "pipeline",
            "error": str(e),
            "code": "FATAL_PIPELINE_ERROR"
        })
        task_store.set_status(task_id, f"Error: {str(e)}")
        task_store.save_results(task_id, report)


def apply_approved_plugin_fixes(task_id, approved_action_ids, approved_page_keywords, deploy_config):
    """
    Second phase of the plugin: apply only WHAT the user approved.
    """
    from urllib.parse import urlparse

    task_store = TaskStore()
    report = task_store.get_results(task_id)
    if not report:
        return

    def progress(msg):
        logger.info("[plugin-apply:%s] %s", task_id, msg)
        task_store.set_status(task_id, msg)

    report["state"] = "deploying"
    
    try:
        # 1. Apply HTML Fixes
        suggested = report.get("suggested_actions", [])
        # We use the loop index (str) as the ID provided by the UI
        actions = []
        for idx_str in approved_action_ids:
            try:
                idx = int(idx_str)
                if 0 <= idx < len(suggested):
                    actions.append(suggested[idx])
            except ValueError:
                continue

        # Get pages from engine_result
        engine_result = report.get("engine_result", {})
        pages = engine_result.get("pages", [])
        page_html_map = {p["url"]: p.get("html", "") for p in pages}
        domain = urlparse(report["site_url"]).netloc

        progress(f"Deploying {len(actions)} approved fixes...")
        
        actions_by_url = _group_actions_by_url(actions)
        for url, url_actions in actions_by_url.items():
            original_html = page_html_map.get(url, "")
            if not original_html:
                # If HTML is missing from engine_result, we can't apply fixes locally
                # In a real scenario, we might re-fetch, but for this plugin we assume engine_result has it
                continue
            
            fixed_html = apply_fixes(original_html, url_actions)
            file_path = _url_to_file_path(url, domain)
            deploy_result = deploy(file_path, fixed_html, deploy_config)
            report["fixes_applied"].append({"url": url, "actions": len(url_actions)})

        # 2. Deploy Generated Pages
        pages_to_gen = [p for p in report.get("pages_generated", []) if p["keyword"] in approved_page_keywords]
        progress(f"Deploying {len(pages_to_gen)} new pages...")
        
        for pg in pages_to_gen:
            file_path = f"{pg['slug']}/index.html"
            deploy(file_path, pg["html"], deploy_config)
            pg["deployed"] = True

        report["state"] = "completed"
        report["completed_at"] = datetime.utcnow().isoformat()
        progress("Deployment finished successfully.")
        task_store.save_results(task_id, report)

    except Exception as e:
        logger.error("Deployment failed: %s", str(e))
        task_store.set_status(task_id, f"Deployment Error: {str(e)}")
        # Save the partial report even on error
        task_store.save_results(task_id, report)


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def _crawl(site_url, crawl_options):
    from urllib.parse import urlparse
    from src.utils.url_utils import build_clean_urls
    
    use_js = crawl_options.get("use_js", False)
    limit = crawl_options.get("limit", 100)
    domain = urlparse(site_url).netloc

    if use_js:
        from src.crawler_engine.js_crawler import crawl_js_sync
        from src.crawler_engine.graph import CrawlGraph
        pages = crawl_js_sync(site_url, limit=limit)
        graph = CrawlGraph()
    else:
        from src.crawler_engine.crawler import crawl
        pages, graph = crawl(site_url, limit=limit)
    
    # Also add sitemap URLs but respect limit
    from src.services.sitemap_parser import get_sitemap_urls
    sitemap_urls = get_sitemap_urls(site_url)
    for url in sitemap_urls:
        if len(pages) >= limit:
            break
        if not any(p["url"] == url for p in pages):
            pages.append({"url": url, "status": 200, "html": ""})
        
    from src.utils.url_utils import build_clean_urls
    clean_urls = build_clean_urls(pages)

    return pages, clean_urls, domain, graph


def _group_actions_by_url(actions):
    by_url = {}
    for action in actions:
        url = action.get("url")
        if url:
            by_url.setdefault(url, []).append(action)
    return by_url


def _url_to_file_path(url, domain):
    path = url.replace(domain, "").strip("/")
    if not path:
        return "index.html"
    if not path.endswith(".html"):
        path = f"{path}/index.html"
    return path


def _extract_keyword_gaps(results, competitors):
    if not competitors:
        return []
    keyword_gap_result = results.get("modules", {}).get("keyword_gap", {})
    gaps = keyword_gap_result.get("keyword_gap", {})
    all_gaps = []
    for kw_list in gaps.values():
        all_gaps.extend(kw_list)
    # Deduplicate
    seen = set()
    unique = []
    for kw in all_gaps:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique


def _get_title(page):
    from bs4 import BeautifulSoup
    html = page.get("html", "")
    if not html:
        return page.get("url", "")
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("title")
    return title.text.strip() if title else page.get("url", "")


def _estimate_score_after(score_before, fixes_count):
    """Estimate improved score — each fix gives a small boost."""
    if score_before is None:
        return None
    improvement = min(fixes_count * 2, 30)  # cap at +30 points
    return min(score_before + improvement, 100)
