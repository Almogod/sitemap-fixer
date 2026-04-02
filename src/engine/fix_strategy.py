def build_fix_strategy(engine_results):

    modules = engine_results.get("modules", {})

    strategy = []

    for module_name, result in modules.items():

        if not result:
            continue

        issues = result.get("issues")
        if not issues:
            continue

        has_actual_issues = False
        if isinstance(issues, dict):
            # Legacy format: {"missing_title": [url1, url2]}
            if any(len(v) > 0 for v in issues.values()):
                has_actual_issues = True
        elif isinstance(issues, list):
            # Enriched or simple list format
            for issue in issues:
                if not isinstance(issue, dict):
                    has_actual_issues = True # fallback for primitive lists
                    break
                
                # If it has a pages list, it must not be empty
                if "pages" in issue:
                    if len(issue.get("pages", [])) > 0:
                        has_actual_issues = True
                        break
                else:
                    # Site-wide issue is always actionable
                    has_actual_issues = True
                    break

        if has_actual_issues:
            strategy.append(module_name)

    return strategy
