def detect_site_type(pages):

    html = pages[0].get("html","")

    if "next.js" in html:
        return "nextjs"

    if "wordpress" in html:
        return "wordpress"

    if "shopify" in html:
        return "shopify"

    return "generic"
