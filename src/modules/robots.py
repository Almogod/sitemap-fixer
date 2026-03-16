import httpx
from src.utils.logger import logger

def run(context):
    domain = context.get("domain", "")
    site_url = context.get("site_url", f"https://{domain}")
    
    issues = []
    suggestions = []
    
    # 1. Try to fetch existing robots.txt
    existing_content = ""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{site_url.rstrip('/')}/robots.txt")
            if resp.status_code == 200:
                existing_content = resp.text
                logger.info("Fetched existing robots.txt")
    except Exception as e:
        logger.warning(f"Could not fetch existing robots.txt: {e}")

    # 2. Check for missing Sitemap directive
    sitemap_url = f"{site_url.rstrip('/')}/sitemap.xml"
    if "Sitemap:" not in existing_content:
        issues.append({
            "issue": "missing_sitemap_in_robots",
            "suggested_sitemap": sitemap_url
        })
        
    # 3. Check for broad Disallow
    if "Disallow: /" in existing_content and "Allow: /" not in existing_content:
        # Note: This is a simplistic check, but good for common errors
        if "User-agent: *" in existing_content:
            issues.append({
                "issue": "broad_disallow_detected",
                "severity": "High"
            })

    # 4. Generate improved content
    if not existing_content:
        new_content = f"User-agent: *\nAllow: /\n\nSitemap: {sitemap_url}"
    else:
        # If missing sitemap, append it
        if "Sitemap:" not in existing_content:
            new_content = existing_content.strip() + f"\n\nSitemap: {sitemap_url}"
        else:
            new_content = existing_content

    # 5. Support dry-run or write
    # In some contexts, we might only want to suggest, but here we write as per original code
    try:
        with open("robots.txt", "w") as f:
            f.write(new_content.strip())
    except Exception as e:
        logger.error(f"Failed to write robots.txt: {e}")
        
    return {
        "status": "success",
        "issues": issues,
        "current_content": existing_content,
        "new_content": new_content
    }
