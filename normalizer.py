from urllib.parse import urlparse, urlunparse, parse_qs

def normalize(url):
    parsed = urlparse(url)

    # remove tracking params
    query = parse_qs(parsed.query)
    clean_query = {k: v for k, v in query.items() if not k.startswith("utm")}

    return urlunparse((
        "https",
        parsed.netloc,
        parsed.path.rstrip("/"),
        "",
        "",
        ""
    ))
