# src/modules/meta.py

from bs4 import BeautifulSoup


def run(context):
    """
    Standard module interface.
    Receives context from engine and returns structured result.
    """

    pages = context["pages"]

    # Standardized enriched issue format
    enriched_issues = [
        {"type": "missing_title", "severity": "critical", "pages": []},
        {"type": "missing_description", "severity": "major", "pages": []},
        {"type": "missing_h1", "severity": "major", "pages": []},
        {"type": "multiple_h1", "severity": "minor", "pages": []}
    ]

    # Helper to find issue in list
    def get_issue(issue_type):
        for i in enriched_issues:
            if i["type"] == issue_type: return i
        return None

    fixes = {}

    for page in pages:
        html = page.get("html")
        url = page.get("url")
        if not html: continue

        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        desc_tag = soup.find("meta", attrs={"name": "description"})
        h1_tags = soup.find_all("h1")

        if not title_tag or not title_tag.text.strip():
            get_issue("missing_title")["pages"].append(url)
            title = generate_title(url, soup)
        else:
            title = title_tag.text.strip()

        if not desc_tag or not desc_tag.get("content"):
            get_issue("missing_description")["pages"].append(url)
            description = generate_description(soup)
        else:
            description = desc_tag.get("content")

        if not h1_tags:
            get_issue("missing_h1")["pages"].append(url)

        if len(h1_tags) > 1:
            get_issue("multiple_h1")["pages"].append(url)

        fixes[url] = {
            "title": title[:60],
            "description": description[:155]
        }

    return {
        "issues": enriched_issues,
        "fixes": fixes
    }


# ------------------------------------
# TITLE GENERATOR
# ------------------------------------
def generate_title(url, soup):

    h1 = soup.find("h1")

    if h1 and h1.text.strip():
        return h1.text.strip()

    slug = url.rstrip("/").split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ")

    if slug:
        return slug.title()

    return "Untitled Page"


# ------------------------------------
# DESCRIPTION GENERATOR
# ------------------------------------
def generate_description(soup):

    paragraph = soup.find("p")

    if paragraph and paragraph.text.strip():
        text = paragraph.text.strip()
        return text[:155]

    return "Learn more about this page."
