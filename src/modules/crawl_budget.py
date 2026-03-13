from collections import deque

MAX_DEPTH = 3


def run(context):

    graph = context["graph"]
    pages = context["pages"]
    domain = context["domain"]

    issues = {
        "deep_pages": [],
        "wasted_crawl_budget": []
    }

    suggestions = []

    # --------------------------
    # build url status map
    # --------------------------
    status_map = {}

    for p in pages:
        url = p.get("url")
        status = p.get("status", 0)
        status_map[url] = status

    # --------------------------
    # compute crawl depth
    # --------------------------
    depth_map = compute_depth(graph, domain)

    for url, depth in depth_map.items():

        if depth > MAX_DEPTH:
            issues["deep_pages"].append({
                "url": url,
                "depth": depth
            })

            suggestions.append({
                "type": "internal_link_boost",
                "target": url,
                "reason": "Page too deep in crawl structure"
            })

    # --------------------------
    # detect crawl budget waste
    # --------------------------
    for url, status in status_map.items():

        if status >= 400:
            issues["wasted_crawl_budget"].append(url)

            suggestions.append({
                "type": "remove_or_fix",
                "target": url,
                "reason": "Broken page consuming crawl budget"
            })

    return {
        "issues": issues,
        "suggestions": suggestions
    }


def compute_depth(graph, start_url):

    depth_map = {}
    queue = deque()

    queue.append((start_url, 0))
    visited = set()

    while queue:

        url, depth = queue.popleft()

        if url in visited:
            continue

        visited.add(url)
        depth_map[url] = depth

        for link in graph.get_outgoing(url):
            queue.append((link, depth + 1))

    return depth_map
