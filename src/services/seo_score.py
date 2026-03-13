def compute_score(engine_results):

    score = 100

    for module, result in engine_results["modules"].items():

        if not result:
            continue

        issues = result.get("issues", [])

        score -= min(len(issues) * 2, 20)

    return max(score, 0)
