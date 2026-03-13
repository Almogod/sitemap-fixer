def verify_fixes(before, after):

    improvement = {}

    improvement["issues_before"] = len(before.get("issues", []))
    improvement["issues_after"] = len(after.get("issues", []))

    improvement["score_change"] = (
        improvement["issues_before"] -
        improvement["issues_after"]
    )

    return improvement
