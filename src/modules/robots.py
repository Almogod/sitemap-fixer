# src/engine/engine.py

from src.audit import generate_audit_report
from src.engine.planner import build_fix_plan
from src.engine.registry import MODULE_REGISTRY
from src.utils.logger import logger


def run_engine(pages, clean_urls, domain):

    context = {
        "pages": pages,
        "urls": clean_urls,
        "domain": domain
    }

    logger.info("Starting SEO engine")

    # -----------------------------
    # RUN AUDIT
    # -----------------------------
    audit = generate_audit_report(pages, clean_urls)

    logger.info("Audit complete")

    # -----------------------------
    # BUILD EXECUTION PLAN
    # -----------------------------
    plan = build_fix_plan(audit)

    logger.info(f"Execution plan: {plan}")

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
            logger.warning(f"Module not found: {module_name}")
            continue

        logger.info(f"Running module: {module_name}")

        try:
            module_result = module.run(context)

            results["modules"][module_name] = module_result

            if module_result and "urls" in module_result:
                context["urls"] = module_result["urls"]

        except Exception as e:
            logger.error(f"Module failed: {module_name} | {str(e)}")

            results["modules"][module_name] = {
                "error": str(e)
            }

    # -----------------------------
    # FINAL URL OUTPUT
    # -----------------------------
    results["fixed_urls"] = context["urls"]

    logger.info("Engine finished")

    return results
