# src/engine/engine.py

from src.services.audit import generate_audit_report
from src.engine.planner import build_fix_plan
from src.engine.registry import MODULE_REGISTRY
from src.engine.fix_strategy import build_fix_strategy
from src.engine.fix_executor import execute_fixes
from src.services.seo_score import compute_score
from src.utils.logger import logger


def run_engine(pages, clean_urls, domain, graph, competitors=None, progress_callback=None):
    """
    Core SEO repair engine.
    Executes analysis modules, builds fix strategy, and generates actionable fixes.
    """

    # -----------------------------
    # INITIAL CONTEXT
    # -----------------------------
    context = {
        "pages": pages,
        "urls": clean_urls,
        "domain": domain,
        "graph": graph,
        "competitors": competitors or []
    }

    logger.info("SEO engine started")

    # -----------------------------
    # RUN AUDIT
    # -----------------------------
    if progress_callback:
        progress_callback("Running site audit...")

    audit = generate_audit_report(pages, clean_urls)

    # -----------------------------
    # BUILD EXECUTION PLAN
    # -----------------------------
    if progress_callback:
        progress_callback("Building execution plan...")

    plan = build_fix_plan(audit)

    results = {
        "audit": audit,
        "plan": plan,
        "modules": {},
        "fixed_urls": clean_urls
    }

    # -----------------------------
    # EXECUTE MODULES
    # -----------------------------
    for module_name in plan:

        module = MODULE_REGISTRY.get(module_name)

        if not module:
            logger.warning("Module %s not found in registry", module_name)
            continue

        logger.info("Running module: %s", module_name)

        if progress_callback:
            progress_callback(f"Running module: {module_name}...")

        try:
            module_result = module.run(context)

            results["modules"][module_name] = module_result

            # modules can update normalized URLs
            if isinstance(module_result, dict) and "urls" in module_result:
                context["urls"] = module_result["urls"]

        except Exception as e:
            logger.error(f"Module {module_name} failed: {e}", exc_info=True)
            results["modules"][module_name] = {
                "error": str(e),
                "code": f"MODULE_EXECUTION_ERROR_{module_name.upper()}",
                "context": {"module": module_name}
            }

    # -----------------------------
    # FIX STRATEGY
    # -----------------------------
    if progress_callback:
        progress_callback("Building fix strategy...")

    strategy = build_fix_strategy(results)

    # -----------------------------
    # EXECUTE FIXES
    # -----------------------------
    if progress_callback:
        progress_callback("Generating automated fixes...")

    actions = execute_fixes(context, results["modules"], strategy)

    results["strategy"] = strategy
    results["actions"] = actions
    results["fixed_urls"] = context["urls"]

    # -----------------------------
    # COMPUTE SEO SCORE
    # -----------------------------
    results["seo_score"] = compute_score(results)

    logger.info("SEO engine finished")

    return results
