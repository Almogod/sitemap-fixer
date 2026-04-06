# src/services/html_rewriter.py
"""
Applies SEO fix actions directly to page HTML using BeautifulSoup DOM manipulation.
Returns modified HTML ready for deployment.

Handles:
  - inject_into_head (add tags to <head>)
  - inject_into_head_first (prepend to <head>)
  - replace_existing_canonical
  - replace_existing_viewport
  - update_meta (title + description)
  - inject_schema (JSON-LD)
  - add_alt to images
  - add_lazy_loading to images
  - defer_script (add defer attribute)
  - fix_insecure_links (http → https)
  - fix_mixed_content (image src http → https)
"""

from bs4 import BeautifulSoup, Tag
import json
import re


def apply_fixes(html: str, actions: list) -> str:
    """
    Apply a list of fix actions to the HTML string.
    Returns the modified HTML string.
    """
    soup = BeautifulSoup(html, "lxml")
    head = _ensure_head(soup)

    for action in actions:
        action_type = action.get("type")

        try:
            if action_type in ("add_og_tag", "add_twitter_tag", "add_preload",
                               "add_dns_prefetch", "add_charset", "add_viewport",
                               "add_canonical", "add_hreflang", "add_pagination_hints"):
                _inject_tag(soup, head, action.get("tag", ""))

            elif action_type == "inject_into_head":
                tag_str = action.get("tag", "")
                if tag_str:
                    _inject_tag(soup, head, tag_str)

            elif action_type == "inject_into_head_first":
                tag_str = action.get("tag", "")
                if tag_str:
                    _inject_tag_first(soup, head, tag_str)

            elif action_type == "replace_existing_canonical":
                tag_str = action.get("tag", "")
                existing = soup.find("link", rel="canonical")
                if existing and tag_str:
                    existing.decompose()
                _inject_tag(soup, head, tag_str)

            elif action_type == "fix_viewport":
                tag_str = action.get("tag", "")
                existing = soup.find("meta", attrs={"name": "viewport"})
                if existing:
                    existing.decompose()
                _inject_tag(soup, head, tag_str)

            elif action_type == "update_meta":
                _apply_meta_fix(soup, head, action)

            elif action_type in ("inject_schema", "inject_faq_schema",
                                 "inject_breadcrumb_schema"):
                schema = action.get("schema")
                if schema:
                    _inject_schema(soup, head, schema)

            elif action_type == "add_alt":
                img_src = action.get("image", {}).get("src") or action.get("image")
                alt_text = action.get("value", "image")
                for img in soup.find_all("img", src=img_src):
                    img["alt"] = alt_text

            elif action_type == "add_lazy_loading":
                img_src = action.get("image", {}).get("src") or action.get("image")
                for img in soup.find_all("img", src=img_src):
                    img["loading"] = "lazy"

            elif action_type == "defer_script":
                script_src = action.get("script")
                for script in soup.find_all("script", src=script_src):
                    script["defer"] = True

            elif action_type == "fix_insecure_links":
                for a in soup.find_all("a", href=True):
                    if a["href"].startswith("http://"):
                        a["href"] = a["href"].replace("http://", "https://", 1)

            elif action_type == "fix_mixed_content":
                for img in soup.find_all("img", src=True):
                    if img["src"].startswith("http://"):
                        img["src"] = img["src"].replace("http://", "https://", 1)

            elif action_type == "generic_replace":
                pattern = action.get("pattern")
                replacement = action.get("replacement")
                is_regex = action.get("is_regex", False)
                if pattern and replacement:
                    # Note: Full string replacement on soup.decode() is risky but 
                    # effective for 'hardcode fixations' across the whole site.
                    # A better way is element-by-element but this is what was requested.
                    html_str = str(soup)
                    if is_regex:
                        html_str = re.sub(pattern, replacement, html_str, flags=re.IGNORECASE)
                    else:
                        html_str = html_str.replace(pattern, replacement)
                    soup = BeautifulSoup(html_str, "lxml")

            elif action_type == "demote_extra_h1":
                h1s = soup.find_all("h1")
                if len(h1s) > 1:
                    # Keep the first one, demote the rest
                    for h1 in h1s[1:]:
                        h1.name = "h2"

        except Exception as e:
            # Log and continue — never crash on a single fix
            pass

    return str(soup)


def _ensure_head(soup) -> Tag:
    head = soup.find("head")
    if not head:
        html_tag = soup.find("html")
        if html_tag:
            head = soup.new_tag("head")
            html_tag.insert(0, head)
        else:
            head = soup.new_tag("head")
            soup.insert(0, head)
    return head


def _inject_tag(soup, head, tag_str: str):
    """Parse a tag string and append it to <head>."""
    new_tag = BeautifulSoup(tag_str, "html.parser")
    for element in new_tag.contents:
        if hasattr(element, "name") and element.name:
            head.append(element.__copy__())


def _inject_tag_first(soup, head, tag_str: str):
    new_tag = BeautifulSoup(tag_str, "html.parser")
    for element in reversed(list(new_tag.contents)):
        if hasattr(element, "name") and element.name:
            head.insert(0, element.__copy__())


def _apply_meta_fix(soup, head, action: dict):
    # Title
    title_text = action.get("title")
    if title_text:
        title_tag = soup.find("title")
        if title_tag:
            title_tag.string = title_text
        else:
            new_title = soup.new_tag("title")
            new_title.string = title_text
            head.append(new_title)

    # Meta description
    desc_text = action.get("description")
    if desc_text:
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag:
            desc_tag["content"] = desc_text
        else:
            new_meta = soup.new_tag("meta")
            new_meta["name"] = "description"
            new_meta["content"] = desc_text
            head.append(new_meta)


def _inject_schema(soup, head, schema: dict):
    script = soup.new_tag("script")
    script["type"] = "application/ld+json"
    script.string = json.dumps(schema, indent=2)
    head.append(script)
