def compute_score(engine_results):

    score = 100

    modules = engine_results.get("modules", {})

    for module_name, result in modules.items():

        if not result:
            continue

        issues = result.get("issues")

        if not issues:
            continue

        score -= min(len(issues) * 2, 15)

    if score < 0:
        score = 0

    return score
