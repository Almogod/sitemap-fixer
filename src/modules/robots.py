def fix_robots(context):
    domain = context["domain"]

    robots_content = f"""
User-agent: *
Allow: /

Sitemap: {domain}/sitemap.xml
"""

    with open("robots.txt", "w") as f:
        f.write(robots_content.strip())
