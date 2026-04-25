# src/services/github_repo_analyzer.py
"""
GitHub Repository Source Analyzer.
Instead of crawling the GitHub website UI (which is noisy and irrelevant),
this module fetches the actual source files (HTML, CSS, JS) from a repo
via the GitHub API and extracts their content for business analysis.
"""

import httpx
import base64
import re
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
from src.utils.logger import logger
from src.config import config


# File extensions that contain meaningful website content for business analysis
WEBSITE_FILE_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".jsx", ".tsx", ".ts",
    ".json", ".md", ".txt", ".yml", ".yaml", ".xml",
    ".php", ".py", ".rb", ".vue", ".svelte",
}

# Files that typically contain business-relevant metadata
PRIORITY_FILES = [
    "index.html", "index.htm", "home.html",
    "about.html", "about.htm",
    "README.md", "readme.md", "README",
    "package.json", "manifest.json", "site.webmanifest",
    "src/index.html", "public/index.html", "dist/index.html",
    "src/App.jsx", "src/App.tsx", "src/App.js", "src/App.vue",
    "src/pages/index.jsx", "src/pages/index.tsx", "src/pages/index.js",
    "pages/index.jsx", "pages/index.tsx", "pages/index.js",
    "app/page.tsx", "app/page.jsx", "app/page.js",
    "app/layout.tsx", "app/layout.jsx",
]

# Directories to skip entirely (not useful for website business analysis)
SKIP_DIRS = {
    "node_modules", ".git", ".github", "__pycache__", ".venv",
    "venv", "env", ".env", "dist", "build", ".next", ".cache",
    "coverage", ".nyc_output", "test", "tests", "__tests__",
    ".idea", ".vscode", ".husky",
}

# Max file size to fetch (skip large bundles/assets)
MAX_FILE_SIZE_BYTES = 100_000  # 100KB


def is_github_repo_url(url: str) -> bool:
    """Check if a URL points to a GitHub repository."""
    parsed = urlparse(url)
    if "github.com" not in parsed.netloc:
        return False
    
    path_parts = parsed.path.strip("/").split("/")
    # Must have at least owner/repo
    return len(path_parts) >= 2


def parse_github_url(url: str) -> Tuple[str, str, str]:
    """
    Parse a GitHub URL into (owner, repo, branch).
    Handles:
        - https://github.com/owner/repo
        - https://github.com/owner/repo/tree/branch
        - https://owner.github.io/repo  (GitHub Pages)
    """
    parsed = urlparse(url)
    
    # Handle GitHub Pages URLs (owner.github.io)
    if parsed.netloc.endswith(".github.io"):
        owner = parsed.netloc.replace(".github.io", "")
        repo = parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else f"{owner}.github.io"
        return owner, repo, "main"
    
    path_parts = parsed.path.strip("/").split("/")
    owner = path_parts[0] if len(path_parts) > 0 else ""
    repo = path_parts[1] if len(path_parts) > 1 else ""
    
    # Extract branch if provided (e.g., /tree/main or /tree/develop)
    branch = "main"
    if len(path_parts) > 3 and path_parts[2] == "tree":
        branch = path_parts[3]
    
    return owner, repo, branch


async def fetch_repo_tree(owner: str, repo: str, branch: str = "main", github_token: str = None) -> List[Dict]:
    """
    Fetch the full file tree of a GitHub repo using the Git Trees API.
    Returns a list of file entries with path, size, and sha.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "UrlForge-SEO-Engine/1.0"
    }
    
    # Use token if available (higher rate limits)
    token = github_token or (config.GITHUB_TOKEN.get_secret_value() if config.GITHUB_TOKEN else None)
    if token and len(token) > 10:
        headers["Authorization"] = f"token {token}"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        
        if resp.status_code == 401 and "Authorization" in headers:
            logger.warning("GitHub API returned 401. Retrying without token...")
            del headers["Authorization"]
            resp = await client.get(url, headers=headers)
            
        if resp.status_code == 404:
            # Try 'master' branch as fallback
            logger.info(f"Branch '{branch}' not found. Trying 'master'...")
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
            resp = await client.get(url, headers=headers)
        
        if resp.status_code != 200:
            logger.error(f"GitHub API error: {resp.status_code} - {resp.text[:200]}")
            return []
        
        data = resp.json()
        tree = data.get("tree", [])
        
        # Filter to relevant files only
        relevant_files = []
        for item in tree:
            if item["type"] != "blob":
                continue
            
            path = item["path"]
            
            # Skip files in excluded directories
            path_parts = path.split("/")
            if any(part in SKIP_DIRS for part in path_parts):
                continue
            
            # Check file extension
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext not in WEBSITE_FILE_EXTENSIONS:
                continue
            
            # Skip files that are too large
            size = item.get("size", 0)
            if size > MAX_FILE_SIZE_BYTES:
                logger.debug(f"Skipping large file: {path} ({size} bytes)")
                continue
            
            relevant_files.append({
                "path": path,
                "sha": item["sha"],
                "size": size,
                "url": item.get("url", "")
            })
        
        logger.info(f"Found {len(relevant_files)} relevant source files in {owner}/{repo}")
        return relevant_files


async def fetch_file_content(owner: str, repo: str, path: str, branch: str = "main", github_token: str = None) -> str:
    """
    Fetch the raw content of a single file from a GitHub repo.
    Uses the raw content endpoint for efficiency.
    """
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "UrlForge-SEO-Engine/1.0"
    }
    
    token = github_token or (config.GITHUB_TOKEN.get_secret_value() if config.GITHUB_TOKEN else None)
    if token and len(token) > 10:
        headers["Authorization"] = f"token {token}"
    
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        
        if resp.status_code == 401 and "Authorization" in headers:
            logger.warning("GitHub API returned 401. Retrying without token...")
            del headers["Authorization"]
            resp = await client.get(url, headers=headers)
        
        if resp.status_code != 200:
            return ""
        
        return resp.text


async def analyze_github_repo(
    repo_url: str,
    progress_callback=None,
    github_token: str = None,
    max_files: int = 30
) -> Dict:
    """
    Main entry point: Analyze a GitHub repo by reading its actual source files.
    
    Instead of crawling github.com HTML pages, this:
    1. Uses the GitHub API to list all files in the repo
    2. Prioritizes HTML, CSS, JS, and config files
    3. Fetches their raw content
    4. Returns the combined content ready for LLM analysis
    
    Returns:
        {
            "owner": "user",
            "repo": "repo-name",
            "files_analyzed": [...],
            "combined_content": "...",
            "file_contents": {"path": "content", ...},
            "metadata": {...}
        }
    """
    owner, repo, branch = parse_github_url(repo_url)
    
    if not owner or not repo:
        return {"error": f"Could not parse GitHub URL: {repo_url}"}
    
    if progress_callback:
        progress_callback(f"Fetching file tree for {owner}/{repo}...")
    
    # Step 1: Get the full file tree
    files = await fetch_repo_tree(owner, repo, branch, github_token)
    
    if not files:
        # Try master branch
        files = await fetch_repo_tree(owner, repo, "master", github_token)
    
    if not files:
        return {"error": f"Could not fetch file tree for {owner}/{repo}. Check if the repo is public."}
    
    # Step 2: Prioritize files — fetch priority files first, then by relevance
    priority_set = set(PRIORITY_FILES)
    priority_files = [f for f in files if f["path"] in priority_set]
    other_files = [f for f in files if f["path"] not in priority_set]
    
    # Sort other files: HTML/HTM first, then JSX/TSX, then CSS, then others
    def file_priority(f):
        path = f["path"].lower()
        if path.endswith((".html", ".htm")):
            return 0
        elif path.endswith((".jsx", ".tsx", ".vue", ".svelte")):
            return 1
        elif path.endswith((".js", ".ts")):
            return 2
        elif path.endswith(".css"):
            return 3
        elif path.endswith((".json", ".md")):
            return 4
        return 5
    
    other_files.sort(key=file_priority)
    ordered_files = priority_files + other_files
    files_to_fetch = ordered_files[:max_files]
    
    if progress_callback:
        progress_callback(f"Fetching {len(files_to_fetch)} source files from {owner}/{repo}...")
    
    # Step 3: Fetch content of each file
    file_contents = {}
    files_analyzed = []
    
    for i, file_info in enumerate(files_to_fetch):
        path = file_info["path"]
        
        if progress_callback and i % 5 == 0:
            progress_callback(f"Reading source files: {i+1}/{len(files_to_fetch)} ({path})...")
        
        content = await fetch_file_content(owner, repo, path, branch, github_token)
        
        if content:
            file_contents[path] = content
            files_analyzed.append({
                "path": path,
                "size": len(content),
                "type": path.rsplit(".", 1)[-1].lower() if "." in path else "unknown"
            })
    
    if progress_callback:
        progress_callback(f"Read {len(file_contents)} source files. Building analysis context...")
    
    # Step 4: Build combined content for LLM analysis
    combined_content = _build_combined_content(file_contents, owner, repo)
    
    # Step 5: Extract metadata from package.json if available
    metadata = _extract_metadata(file_contents)
    
    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "files_analyzed": files_analyzed,
        "combined_content": combined_content,
        "file_contents": file_contents,
        "metadata": metadata,
        "total_files_in_repo": len(files),
        "files_fetched": len(file_contents),
    }


def _build_combined_content(file_contents: Dict[str, str], owner: str, repo: str) -> str:
    """
    Build a structured combined text from all file contents.
    This is optimized for LLM consumption — giving the model a clear picture
    of the website's structure and content.
    """
    sections = []
    
    sections.append(f"=== REPOSITORY: {owner}/{repo} ===\n")
    sections.append(f"Total source files analyzed: {len(file_contents)}\n")
    
    # Group files by type
    html_files = {}
    component_files = {}
    style_files = {}
    config_files = {}
    doc_files = {}
    other_files = {}
    
    for path, content in file_contents.items():
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else "unknown"
        
        if ext in ("html", "htm"):
            html_files[path] = content
        elif ext in ("jsx", "tsx", "vue", "svelte"):
            component_files[path] = content
        elif ext in ("css", "scss", "less"):
            style_files[path] = content
        elif ext in ("json", "yml", "yaml", "xml"):
            config_files[path] = content
        elif ext in ("md", "txt"):
            doc_files[path] = content
        else:
            other_files[path] = content
    
    # Build structured output
    if html_files:
        sections.append("\n--- HTML PAGES (Website Structure & Content) ---")
        for path, content in html_files.items():
            sections.append(f"\n### FILE: {path}")
            sections.append(content[:6000])  # Cap per file
    
    if component_files:
        sections.append("\n--- UI COMPONENTS (Application Logic & UI Text) ---")
        for path, content in component_files.items():
            sections.append(f"\n### FILE: {path}")
            sections.append(content[:5000])
    
    if doc_files:
        sections.append("\n--- DOCUMENTATION (Project Description & Purpose) ---")
        for path, content in doc_files.items():
            sections.append(f"\n### FILE: {path}")
            sections.append(content[:4000])
    
    if config_files:
        sections.append("\n--- CONFIGURATION (Metadata & Dependencies) ---")
        for path, content in config_files.items():
            sections.append(f"\n### FILE: {path}")
            sections.append(content[:3000])
    
    if style_files:
        sections.append("\n--- STYLES (Design System & Branding) ---")
        for path, content in style_files.items():
            sections.append(f"\n### FILE: {path}")
            # CSS is less critical for business analysis — keep it shorter
            sections.append(content[:2000])
    
    if other_files:
        sections.append("\n--- OTHER SOURCE FILES ---")
        for path, content in list(other_files.items())[:5]:  # Limit
            sections.append(f"\n### FILE: {path}")
            sections.append(content[:2000])
    
    return "\n".join(sections)


def _extract_metadata(file_contents: Dict[str, str]) -> Dict:
    """
    Extract project metadata from common config files.
    """
    metadata = {
        "name": "",
        "description": "",
        "keywords": [],
        "dependencies": [],
        "homepage": "",
        "author": "",
    }
    
    # Try package.json
    pkg_json = file_contents.get("package.json", "")
    if pkg_json:
        try:
            import json
            pkg = json.loads(pkg_json)
            metadata["name"] = pkg.get("name", "")
            metadata["description"] = pkg.get("description", "")
            metadata["keywords"] = pkg.get("keywords", [])
            metadata["homepage"] = pkg.get("homepage", "")
            metadata["author"] = pkg.get("author", "") if isinstance(pkg.get("author"), str) else pkg.get("author", {}).get("name", "")
            
            # Get key dependencies (for tech stack analysis)
            deps = list(pkg.get("dependencies", {}).keys())
            dev_deps = list(pkg.get("devDependencies", {}).keys())
            metadata["dependencies"] = deps[:20]
            metadata["dev_dependencies"] = dev_deps[:20]
        except Exception as e:
            logger.debug(f"Could not parse package.json: {e}")
    
    # Try README for description
    readme = file_contents.get("README.md", "") or file_contents.get("readme.md", "")
    if readme and not metadata["description"]:
        # Take the first meaningful paragraph as description
        lines = readme.split("\n")
        for line in lines:
            clean = line.strip().strip("#").strip()
            if len(clean) > 30 and not clean.startswith("!["): 
                metadata["description"] = clean[:300]
                break
    
    return metadata
