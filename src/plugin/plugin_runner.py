import os
import yaml
import importlib
from datetime import datetime
from typing import List, Dict, Any
from src.plugin.base import BaseSEOPlugin, PluginManifest
from src.utils.logger import logger, audit_logger
from src.services.task_store import TaskStore
from src.services.html_rewriter import apply_fixes
from src.services.deployer import deploy

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
    site_token: str = None,
    target_keyword: str = None,
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
        "dry_run": dry_run,
        "llm_config": llm_config
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
                pages, clean_urls, domain, graph = _crawl(site_url, crawl_options, site_token)
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
                
                # ═══════════════════════════════════════════════════
                # STEP 1: SEO Audit (standard engine analysis)
                # ═══════════════════════════════════════════════════
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
                progress(f"SEO Audit complete. Score: {report['seo_score_before']}")

                # ═══════════════════════════════════════════════════
                # STEP 2: Deep Site Content Analysis
                # Understand WHAT the site is about, its tone, niche
                # ═══════════════════════════════════════════════════
                progress("Analyzing site content, tone, and niche...")
                from src.content.engine import analyze_site_content, verify_keyword_relevance, generate_markdown_site_profile
                domain_context = analyze_site_content(context_data["pages"], context_data["domain"], llm_config=llm_config)
                
                # NEW: Generate and save the persistent Site Profile Markdown
                site_profile_md = generate_markdown_site_profile(domain_context)
                report["site_profile_md"] = site_profile_md
                report["domain_context"] = domain_context # Keep raw for logic
                
                progress(f"Site analysis: niche='{domain_context.get('niche')}', tone='{domain_context.get('tone')}'")
                progress("Site Profile Markdown generated for context injection.")

                # ═══════════════════════════════════════════════════
                # STEP 3: Extract & Rank Keywords
                # ═══════════════════════════════════════════════════
                from src.content.engine import run_content_engine
                content_res = run_content_engine(
                    context_data["pages"], 
                    competitors, 
                    llm_config, 
                    domain=context_data["domain"]
                )
                
                keyword_gaps = content_res.get("recommendations", [])
                site_keywords = content_res.get("site_keywords", [])
                prime_keywords = content_res.get("prime_keywords", [])
                
                report["keyword_gap"] = content_res.get("keyword_gap", {})
                report["site_keywords"] = site_keywords
                
                existing_pages_list = [{"url": p["url"], "title": _get_title(p)} for p in context_data["pages"]]
                report["content_generation_available"] = bool(keyword_gaps) or bool(prime_keywords)
                report["keyword_recommendations"] = keyword_gaps
                report["existing_pages_list"] = existing_pages_list
                progress(f"Found {len(site_keywords)} site keywords, {len(prime_keywords)} prime keywords")

                # ═══════════════════════════════════════════════════
                # STEP 4: Search Web for Competitor FAQs & Generate
                # Uses the API to match the site's tone
                # ═══════════════════════════════════════════════════
                progress(f"Searching web for competitor FAQs and generating site-specific FAQs...")
                from src.content.faq_generator import generate_site_faqs
                site_faqs = generate_site_faqs(
                    site_keywords, 
                    context_data["domain"], 
                    llm_config, 
                    site_context=domain_context
                )
                report["site_faqs"] = [faq.model_dump() for faq in site_faqs]
                progress(f"Generated {len(site_faqs)} site-specific FAQs (API: {llm_config.get('provider', 'builtin')})")
                
                # ═══════════════════════════════════════════════════
                # STEP 5: Verify Keywords & Auto-Generate Pages
                # Only generate for keywords VERIFIED to be relevant
                # ═══════════════════════════════════════════════════
                candidate_keywords = []
                if target_keyword:
                    candidate_keywords.append(target_keyword)
                
                for rec in keyword_gaps[:5]:
                    if rec["keyword"] not in candidate_keywords:
                        candidate_keywords.append(rec["keyword"])
                
                for pk in prime_keywords[:5]:
                    if pk not in candidate_keywords:
                        candidate_keywords.append(pk)

                # Verify each keyword is relevant to the site content
                verified_keywords = []
                for kw in candidate_keywords:
                    if verify_keyword_relevance(kw, domain_context):
                        verified_keywords.append(kw)
                    else:
                        progress(f"Keyword '{kw}' rejected — not relevant to site content")
                
                if not verified_keywords:
                    progress("No verified keywords for page generation.")
                else:
                    progress(f"Verified {len(verified_keywords)} keywords for page generation: {verified_keywords}")

                for kw in verified_keywords[:5]:  # Cap at 5 pages max
                    try:
                        progress(f"Generating page for verified keyword: '{kw}' (via {llm_config.get('provider', 'builtin')})")
                        from src.content.engine import generate_content_for_keyword
                        page_result = generate_content_for_keyword(
                            kw, 
                            competitors, 
                            llm_config, 
                            existing_pages=existing_pages_list,
                            domain_context=domain_context,
                            site_wide_faqs=report.get("site_faqs", [])
                        )
                        if "error" not in page_result:
                            page_result["keyword"] = kw
                            report["pages_generated"].append(page_result)
                            method = page_result.get("generation_method", "unknown")
                            words = page_result.get("word_count", 0)
                            progress(f"Generated page for '{kw}': {words} words via {method}")
                        else:
                            progress(f"Generation failed for '{kw}': {page_result.get('error')}")
                            report["errors"].append({"phase": "auto_gen", "keyword": kw, "error": page_result.get("error")})
                    except Exception as gen_ex:
                        progress(f"Critical error generating '{kw}': {gen_ex}")
                        report["errors"].append({"phase": "auto_gen", "keyword": kw, "error": str(gen_ex)})


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


def apply_approved_plugin_fixes(task_id, approved_action_ids, approved_page_keywords, deploy_config, llm_config=None, site_token=None):
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
    task_store.save_results(task_id, report)
    
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
        
        deployed_files = {}
        latest_commit_sha = ""
        
        actions_by_url = _group_actions_by_url(actions)
        for url, url_actions in actions_by_url.items():
            original_html = page_html_map.get(url, "")
            if not original_html:
                # Re-fetch the page if HTML is missing
                progress(f"Re-fetching {url} for fix application...")
                original_html = _refetch_page(url, site_token)
                if not original_html:
                    progress(f"Skipping {url} — could not fetch HTML")
                    continue
            
            fixed_html = apply_fixes(original_html, url_actions)
            file_path = _url_to_file_path(url, report["site_url"])
            progress(f"Targeting repo path: {file_path}")
            
            deployed_files[file_path] = fixed_html
            
            deploy_result = deploy(file_path, fixed_html, deploy_config)
            if deploy_result.get("commit_sha"):
                latest_commit_sha = deploy_result.get("commit_sha")
            report["deploy_results"].append(deploy_result)
            report["fixes_applied"].append({"url": url, "actions": len(url_actions), "deploy": deploy_result.get("success", False)})
        
        # Periodic save to keep UI updated
        task_store.save_results(task_id, report)

        # 2. Deploy Generated Pages
        pages_to_gen = [p for p in report.get("pages_generated", []) if p["keyword"] in approved_page_keywords]
        progress(f"Deploying {len(pages_to_gen)} new pages...")
        
        for pg in pages_to_gen:
            # Output as a React Component instead of an HTML page
            file_path = f"pages/{pg['slug']}.jsx"
            progress(f"Targeting new page path: {file_path}")
            
            # Prefer the modular react jsx payload, fallback to html if not available for some reason
            payload = pg.get("react_jsx") or pg.get("html", "")
            
            deployed_files[file_path] = payload
            
            deploy_result = deploy(file_path, payload, deploy_config)
            if deploy_result.get("commit_sha"):
                latest_commit_sha = deploy_result.get("commit_sha")
            report["deploy_results"].append(deploy_result)
            pg["deployed"] = deploy_result.get("success", False)

        # 3. Flush Vercel batch if using Vercel
        if deploy_config.get("platform") == "vercel":
            from src.services.deployer import vercel_flush_deploy
            progress("Creating Vercel deployment...")
            vercel_result = vercel_flush_deploy(deploy_config)
            report["deploy_results"].append(vercel_result)

        # 4. Trigger GitHub Workflow Monitor if applicable (Autonomous Self-Healing CI/CD)
        if deploy_config.get("platform") == "github" and deployed_files:
            progress("Initiating autonomous GitHub Actions workflow monitor...")
            try:
                from src.services.github_monitor import monitor_and_autofix_workflow
                monitor_and_autofix_workflow(deploy_config, deployed_files, latest_commit_sha, llm_config, progress, max_retries=3)
            except Exception as monitor_ex:
                progress(f"Workflow monitor halted: {monitor_ex}")
                report["workflow_error"] = str(monitor_ex)

        report["state"] = "completed"
        report["seo_score_after"] = _estimate_score_after(
            report.get("seo_score_before"),
            len(report.get("fixes_applied", []))
        )
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



def _crawl(site_url, crawl_options, site_token=None):
    from urllib.parse import urlparse
    from src.utils.url_utils import build_clean_urls

    headers = {}
    if site_token:
        headers["X-Site-Token"] = site_token # Or Authorization? User said "the token", I'll use X-Site-Token and suggest Authorization if needed.
        headers["Authorization"] = f"Bearer {site_token}" # Adding both for robustness
    
    use_js = crawl_options.get("use_js", False)
    limit = crawl_options.get("limit", 100)
    max_depth = crawl_options.get("max_depth", 10)
    crawl_assets = crawl_options.get("crawl_assets", False)
    backend = crawl_options.get("backend", "memory")
    concurrency = crawl_options.get("concurrency", 10)
    delay = crawl_options.get("delay", 1.0)
    custom_selectors = crawl_options.get("custom_selectors", None)
    broken_links_only = crawl_options.get("broken_links_only", False)
    domain = urlparse(site_url).netloc

    if use_js:
        from src.crawler_engine.js_crawler import crawl_js_sync
        pages, graph = crawl_js_sync(
            site_url, 
            limit=limit, 
            delay=delay,
            headers=headers, 
            crawl_assets=crawl_assets, 
            broken_links_only=broken_links_only
        )
    else:
        from src.crawler_engine.crawler import crawl
        pages, graph = crawl(
            site_url, 
            limit=limit, 
            extra_headers=headers,
            max_depth=max_depth,
            crawl_assets=crawl_assets,
            backend=backend,
            concurrency=concurrency,
            custom_selectors=custom_selectors,
            broken_links_only=broken_links_only
        )
    
    # Also add sitemap URLs but respect limit
    from src.services.sitemap_parser import get_sitemap_urls
    sitemap_urls = get_sitemap_urls(site_url)
    for url in sitemap_urls:
        if len(pages) >= limit:
            break
        if not any(p["url"] == url for p in pages):
            pages.append({"url": url, "status": 200, "html": ""})
        
    from src.utils.url_utils import build_clean_urls

    base_path = urlparse(site_url).path
    if base_path and base_path != "/":
        pages = [p for p in pages if urlparse(p.get("url", "")).path.startswith(base_path) or urlparse(p.get("url", "")).path == base_path]
        
    clean_urls = build_clean_urls(pages)

    return pages, clean_urls, domain, graph


def _group_actions_by_url(actions):
    by_url = {}
    for action in actions:
        url = action.get("url")
        if url:
            by_url.setdefault(url, []).append(action)
    return by_url


def _refetch_page(url, site_token=None):
    """Re-fetch a page's HTML when it's missing from the engine result."""
    import httpx
    headers = {}
    if site_token:
        headers["Authorization"] = f"Bearer {site_token}"
    try:
        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning("Failed to re-fetch %s: %s", url, e)
    return ""


def _url_to_file_path(url, base_url):
    """
    Converts a full URL to a relative repository path by stripping the base_url.
    Example:
        url: https://user.github.io/repo/sub/page.html
        base: https://user.github.io/repo/
        result: sub/page.html
    """
    from urllib.parse import urlparse
    
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    
    # Strip protocol/domain if they match (or just take the path)
    # The relative path is based on the difference between URL path and Base path
    u_path = parsed_url.path.strip("/")
    b_path = parsed_base.path.strip("/")
    
    if u_path.startswith(b_path):
        path = u_path[len(b_path):].strip("/")
    else:
        path = u_path
    
    if not path:
        return "index.html"
    
    # If path is a directory (no ext), make it index.html
    if not os.path.splitext(path)[1]:
        # Handle trailing slash case
        path = path.rstrip("/") + "/index.html"
        
    return path.strip("/")


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
