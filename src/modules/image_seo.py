# src/modules/image_seo.py

from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re


MAX_IMAGE_NAME_LENGTH = 60


def run(context):

    pages = context["pages"]

    issues = []
    fixes = {}

    for page in pages:

        url = page.get("url")
        html = page.get("html")

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        images = soup.find_all("img")

        if not images:
            continue

        page_fixes = []

        for img in images:

            src = img.get("src")
            alt = img.get("alt")

            if not src:
                continue

            # --------------------------------
            # Missing ALT text
            # --------------------------------
            if not alt or not alt.strip():

                alt_text = generate_alt_from_filename(src)

                issues.append({
                    "url": url,
                    "issue": "missing_alt",
                    "image": src
                })

                page_fixes.append({
                    "image": src,
                    "fix": "add_alt",
                    "value": alt_text
                })

            # --------------------------------
            # Poor filename
            # --------------------------------
            filename = extract_filename(src)

            if filename and not is_seo_friendly(filename):

                better_name = generate_seo_filename(filename)

                issues.append({
                    "url": url,
                    "issue": "bad_filename",
                    "image": src
                })

                page_fixes.append({
                    "image": src,
                    "fix": "rename_image",
                    "value": better_name
                })

            # --------------------------------
            # Lazy loading
            # --------------------------------
            if not img.get("loading"):

                page_fixes.append({
                    "image": src,
                    "fix": "add_lazy_loading",
                    "value": "loading='lazy'"
                })

        if page_fixes:
            fixes[url] = page_fixes

    return {
        "issues": issues,
        "fixes": fixes
    }


def extract_filename(src):

    parsed = urlparse(src)

    name = parsed.path.split("/")[-1]

    return name


def generate_alt_from_filename(src):

    filename = extract_filename(src)

    name = filename.split(".")[0]

    name = name.replace("-", " ").replace("_", " ")

    return name.title()


def is_seo_friendly(filename):

    name = filename.split(".")[0]

    if len(name) > MAX_IMAGE_NAME_LENGTH:
        return False

    if "_" in name:
        return False

    if re.search(r"[A-Z]", name):
        return False

    return True


def generate_seo_filename(filename):

    name, ext = filename.split(".", 1)

    name = name.replace("_", "-").lower()

    name = re.sub(r"[^a-z0-9\-]", "", name)

    return f"{name}.{ext}"
