from urllib.parse import urlparse, urlunparse, parse_qs

def normalize(url):
    parsed = urlparse(url)

    return urlunparse((
        "https",
        parsed.netloc,
        parsed.path.rstrip("/"),
        "",
        "",
        ""
    ))
