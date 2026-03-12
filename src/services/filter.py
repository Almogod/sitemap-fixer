def is_valid(page):
    return (
        page["status"] == 200 and
        not page["noindex"] and
        page["canonical"] == page["url"]
    )
