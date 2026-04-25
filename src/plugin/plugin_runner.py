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
from src.services.gsc_service import GSCService
from src.services.data_processing_service import process_html_content
from src.services.site_analysis_service import synthesize_business_analysis
from src.services.github_repo_analyzer import is_github_repo_url, analyze_github_repo

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


async def run_plugin(
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
    import asyncio
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

    # Pipeline Adjustment: User requested to remove the scraper and use whole site analysis
    if "crawl" in pipeline:
        pipeline.remove("crawl")

    business_context = {}
    keyword_gaps = []
    prime_keywords = []
    site_phrases = []
    try:
        for phase in pipeline:
            progress(f"Starting phase: {phase}...")
            
            if phase == "analyze":
                # ═══════════════════════════════════════════════════
                # STEP 1: Homepage-Only Business Analysis
                # The homepage contains the core business identity —
                # no need to scrape the entire site for this.
                # ═══════════════════════════════════════════════════
                from src.services.sitemap_parser import get_sitemap_urls
                from src.crawler_engine.fetcher import fetch
                from urllib.parse import urlparse
                import httpx

                context_data["domain"] = urlparse(site_url).netloc

                # Fetch ONLY the homepage for business analysis
                progress("Fetching homepage for Business Analysis...")
                homepage_html = ""
                is_github = is_github_repo_url(site_url)
                
                if is_github:
                    progress("GitHub repository detected. Analyzing source files directly via GitHub API...")
                    github_token = llm_config.get("github_token") if llm_config else None
                    if not github_token:
                        github_token = deploy_config.get("github_token") if deploy_config else None
                        
                    repo_analysis = await analyze_github_repo(site_url, progress, github_token=github_token)
                    if "error" in repo_analysis:
                        progress(f"GitHub API Error: {repo_analysis['error']}")
                        report["errors"].append({"phase": "analyze", "error": repo_analysis['error']})
                    else:
                        homepage_html = repo_analysis.get("combined_content", "")
                        progress(f"Successfully fetched {repo_analysis.get('files_fetched')} source files from {site_url}.")
                        context_data["pages"] = [{
                            "url": site_url,
                            "html": homepage_html,
                            "status": 200
                        }]
                        
                        from src.services.data_processing_service import process_raw_content
                        progress("Extracting business intelligence from repo source code...")
                        homepage_structured = []
                        try:
                            processed = await process_raw_content(site_url, homepage_html, llm_config=llm_config)
                            homepage_structured = processed.get("structured_data", [])
                        except Exception as e:
                            logger.error(f"Repo processing failed: {e}")

                if not is_github or not homepage_html:
                    async with httpx.AsyncClient(timeout=30) as client:
                        try:
                            res = await fetch(client, site_url)
                            if res.get("status") == 200:
                                homepage_html = res.get("html", "")
                                # Seed pages list with homepage
                                context_data["pages"] = [{
                                    "url": site_url,
                                    "html": homepage_html,
                                    "status": 200
                                }]
                        except Exception as e:
                            logger.warning(f"Failed to fetch homepage {site_url}: {e}")

                    if not homepage_html:
                        report["errors"].append({"phase": "analyze", "error": "Could not fetch homepage"})
                        progress("Homepage fetch failed. Skipping business analysis.")
                    else:
                        # Process homepage content into structured data
                        progress("Extracting business intelligence from homepage...")
                        homepage_structured = []
                        try:
                            processed = await process_html_content(site_url, homepage_html, llm_config=llm_config)
                            homepage_structured = processed.get("structured_data", [])
                        except Exception as e:
                            logger.error(f"Homepage processing failed: {e}")

                    # Synthesize business analysis from homepage data only
                    site_analysis = await asyncio.to_thread(
                        synthesize_business_analysis,
                        context_data["domain"], homepage_structured, llm_config=llm_config
                    )
                    site_analysis_report = site_analysis.get("report", "")
                    business_context = site_analysis.get("context", {})

                    report["site_analysis_report"] = site_analysis_report
                    report["business_context"] = business_context

                    progress(f"Business Analysis Complete. Category: {business_context.get('category', 'Unknown')}")

                # ═══════════════════════════════════════════════════
                # STEP 1b: Collect sitemap URLs for SEO audit (not for analysis)
                # ═══════════════════════════════════════════════════
                if not context_data["pages"] or len(context_data["pages"]) < 2:
                    progress("Collecting sitemap URLs for SEO audit...")
                    sitemap_urls = await asyncio.to_thread(get_sitemap_urls, site_url)
                    if sitemap_urls:
                        progress(f"Found {len(sitemap_urls)} URLs in sitemap.")
                        # Add sitemap URLs as lightweight entries (no HTML needed for audit)
                        for url in sitemap_urls:
                            if not any(p["url"] == url for p in context_data["pages"]):
                                context_data["pages"].append({"url": url, "html": "", "status": 200})

                # ═══════════════════════════════════════════════════
                # STEP 3: SEO Audit & Keyword Strategy
                # ═══════════════════════════════════════════════════
                from src.engine.engine import run_engine
                from src.content.engine import run_content_engine
                
                # Standard audit for score
                results = await asyncio.to_thread(
                    run_engine,
                    pages=context_data["pages"],
                    clean_urls=context_data["clean_urls"],
                    domain=context_data["domain"],
                    graph=context_data["graph"],
                    competitors=competitors,
                    progress_callback=progress
                )
                report["seo_score_before"] = results.get("seo_score", 0)
                report["engine_result"] = results
                
                # ═══════════════════════════════════════════════════
                # STEP 3: SEO Audit & Keyword Strategy
                # ═══════════════════════════════════════════════════
                # Before keyword analysis, we need actual content from the sitemap pages
                # (Business Analysis only used the homepage, but keywords need the whole site)
                empty_pages = [p for p in context_data["pages"] if not p.get("html")]
                if empty_pages:
                    progress(f"Fetching content for {len(empty_pages[:50])} sitemap pages for keyword analysis...")
                    async with httpx.AsyncClient(timeout=20) as client:
                        for p in empty_pages[:50]: # Limit to 50 for speed
                            try:
                                res = await fetch(client, p["url"])
                                if res.get("status") == 200:
                                    p["html"] = res.get("html", "")
                            except: pass

                progress("Running Keyword Strategy Engine (Phrase-Aware)...")
                # Only pass pages that actually have HTML content for keyword extraction
                pages_with_content = [p for p in context_data["pages"] if p.get("html")]
                if not pages_with_content:
                    progress("WARNING: No pages with HTML content found. Using homepage only.")
                    pages_with_content = [p for p in context_data["pages"] if p.get("url") == site_url]
                
                progress(f"Analyzing keywords from {len(pages_with_content)} pages with content...")
                content_res = await asyncio.to_thread(
                    run_content_engine,
                    pages_with_content, 
                    competitors, 
                    llm_config, 
                    domain=context_data["domain"]
                )
                
                keyword_gaps = content_res.get("recommendations", [])
                prime_keywords = content_res.get("prime_keywords", [])
                site_phrases = content_res.get("site_phrases", [])
                site_keywords = content_res.get("site_keywords", [])
                report["keyword_recommendations"] = keyword_gaps
                report["site_phrases"] = site_phrases
                report["site_keywords"] = site_keywords
                progress(f"Discovered {len(site_phrases)} phrases and {len(site_keywords)} keywords.")
                

                # ═══════════════════════════════════════════════════
                # STEP 4: Generate FAQs (Driven by Business Analysis + Phrases)
                # ═══════════════════════════════════════════════════
                progress("Generating site-specific FAQs based on Business Analysis...")
                from src.content.faq_generator import generate_site_faqs
                # Use phrase-aware keywords for FAQ generation
                faq_keywords = site_phrases[:10] if site_phrases else content_res.get("site_keywords", [])
                site_faqs = await asyncio.to_thread(
                    generate_site_faqs,
                    faq_keywords, 
                    context_data["domain"], 
                    llm_config, 
                    site_context=business_context # Use new context
                )
                report["site_faqs"] = [faq.model_dump() for faq in site_faqs]
                progress(f"Generated {len(site_faqs)} FAQs.")

                # ═══════════════════════════════════════════════════
                # STEP 5: Generate Pages (Driven by Category)
                # ═══════════════════════════════════════════════════
                candidate_keywords = []
                if target_keyword:
                    candidate_keywords.append(target_keyword)
                candidate_keywords.extend([rec["keyword"] for rec in keyword_gaps[:3]])
                candidate_keywords.extend(prime_keywords[:2])
                
                # Filter duplicates and limit
                verified_keywords = list(dict.fromkeys(candidate_keywords))[:5]
                progress(f"Generating pages for keywords: {verified_keywords}")

                existing_pages_list = [{"url": p["url"], "title": _get_title(p)} for p in context_data["pages"]]
                
                for kw in verified_keywords:
                    try:
                        progress(f"Generating page for '{kw}' (Category: {business_context.get('category')})")
                        from src.content.engine import generate_content_for_keyword
                        page_result = await asyncio.to_thread(
                            generate_content_for_keyword,
                            kw, 
                            competitors, 
                            llm_config, 
                            existing_pages=existing_pages_list,
                            domain_context=business_context, # Use business context
                            site_wide_faqs=report.get("site_faqs", [])
                        )
                        if "error" not in page_result:
                            page_result["keyword"] = kw
                            report["pages_generated"].append(page_result)
                            progress(f"Generated page for '{kw}'")
                    except Exception as gen_ex:
                        logger.error(f"Generation failed for {kw}: {gen_ex}")
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

        # ═══════════════════════════════════════════════════
        # STEP 5: Indexation Fixes (Conditional on GSC)
        # ═══════════════════════════════════════════════════
        gsc_service = GSCService()
        if gsc_service.is_available():
            progress("GSC credentials available. Fixing Indexation issues...")
            gsc_audit = report.get("gsc_audit", {})
            
            # 5.1 Submit Unindexed URLs
            unindexed = gsc_audit.get("unindexed", [])
            submitted_count = 0
            for item in unindexed:
                if gsc_service.submit_for_indexing(item["url"]):
                    submitted_count += 1
            progress(f"Submitted {submitted_count} URLs to Google Indexing API")
            
            # 5.2 Fix Sitemap Gaps
            gaps = gsc_audit.get("gaps", {})
            missing_in_sitemap = gaps.get("missing_in_sitemap", [])
            if missing_in_sitemap:
                progress(f"Fixing sitemap gaps: adding {len(missing_in_sitemap)} URLs...")
                try:
                    # Fetch current sitemap
                    from src.services.sitemap_parser import get_sitemap_urls
                    # We need the raw XML to update it properly
                    sitemap_url = site_url.rstrip("/") + "/sitemap.xml"
                    import httpx
                    res = httpx.get(sitemap_url, timeout=10)
                    if res.status_code == 200:
                        new_sitemap_xml = _add_urls_to_sitemap(res.text, missing_in_sitemap)
                        deploy_res = deploy("sitemap.xml", new_sitemap_xml, deploy_config)
                        if deploy_res.get("success"):
                            progress("Successfully updated sitemap.xml on target site")
                        else:
                            progress(f"Sitemap deployment failed: {deploy_res.get('message')}")
                except Exception as e:
                    progress(f"Failed to fix sitemap automatically: {e}")

            # 5.3 Generate Excel Report
            report_file = f"indexing_report_{task_id}.xlsx"
            gsc_service.generate_excel_report(
                gsc_audit.get("indexed", []),
                gsc_audit.get("unindexed", []),
                report_file
            )
            report["indexing_report_file"] = report_file
            progress(f"Indexing report generated: {report_file}")

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



async def _crawl(site_url, crawl_options, progress_callback=None, site_token=None):
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
    user_agent = crawl_options.get("user_agent", "chrome")
    domain = urlparse(site_url).netloc

    if use_js:
        from src.crawler_engine.js_crawler import crawl_js_sync
        pages, graph = crawl_js_sync(
            site_url, 
            limit=limit, 
            progress_callback=progress_callback,
            delay=delay,
            headers=headers, 
            crawl_assets=crawl_assets, 
            broken_links_only=broken_links_only,
            user_agent=user_agent
        )
    else:
        from src.crawler_engine.crawler import crawl_async
        pages, graph = await crawl_async(
            site_url, 
            limit=limit, 
            progress_callback=progress_callback,
            extra_headers=headers,
            max_depth=max_depth,
            crawl_assets=crawl_assets,
            backend=backend,
            concurrency=concurrency,
            custom_selectors=custom_selectors,
            broken_links_only=broken_links_only,
            user_agent=user_agent
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

def _add_urls_to_sitemap(current_xml: str, new_urls: List[str]) -> str:
    """Helper to inject new <url> entries into sitemap.xml."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(current_xml, "xml")
    urlset = soup.find("urlset")
    if not urlset:
        return current_xml
    
    for url in new_urls:
        url_tag = soup.new_tag("url")
        loc_tag = soup.new_tag("loc")
        loc_tag.string = url
        url_tag.append(loc_tag)
        urlset.append(url_tag)
    
    return str(soup)
