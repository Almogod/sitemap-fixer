# src/services/deployer.py
"""
Deploys fixed HTML files back to the target website.
Supports six deployment strategies:
  - filesystem: write directly to a local path
  - github:     commit files via the GitHub API
  - vercel:     deploy via Vercel Deployments API
  - hostinger:  upload via SFTP (paramiko)
  - ftp:        upload via ftplib
  - webhook:    POST file content to a configured endpoint
"""

import os
import json
import base64
from pathlib import Path
from src.utils.logger import logger


def deploy(file_path: str, content: str, config: dict) -> dict:
    """
    Deploy a single file.

    Args:
        file_path: relative path inside the site (e.g. 'blog/my-post.html')
        content:   full HTML content string
        config:    dict with keys: platform, and platform-specific settings

    Returns:
        dict with: success, platform, file_path, message
    """
    platform = config.get("platform", "filesystem").lower()

    try:
        if platform == "filesystem":
            return _deploy_filesystem(file_path, content, config)
        elif platform == "github":
            return _deploy_github(file_path, content, config)
        elif platform == "vercel":
            return _deploy_vercel(file_path, content, config)
        elif platform == "hostinger":
            return _deploy_hostinger(file_path, content, config)
        elif platform == "ftp":
            return _deploy_ftp(file_path, content, config)
        elif platform == "webhook":
            return _deploy_webhook(file_path, content, config)
        else:
            return {"success": False, "message": f"Unknown platform: {platform}"}
    except Exception as e:
        logger.error("Deploy failed for %s: %s", file_path, str(e))
        return {"success": False, "platform": platform, "file_path": file_path, "message": str(e)}


# ─────────────────────────────────────────────────────────
# FILESYSTEM
# ─────────────────────────────────────────────────────────

def _deploy_filesystem(file_path: str, content: str, config: dict) -> dict:
    base_dir = config.get("base_dir", "./output")
    full_path = Path(base_dir) / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return {
        "success": True,
        "platform": "filesystem",
        "file_path": str(full_path),
        "message": "File written successfully"
    }


# ─────────────────────────────────────────────────────────
# GITHUB API
# ─────────────────────────────────────────────────────────

def _deploy_github(file_path: str, content: str, config: dict) -> dict:
    import httpx

    token = config.get("github_token") or os.environ.get("GITHUB_TOKEN", "")
    repo = config.get("github_repo", "").strip().replace("https://github.com/", "").strip("/")
    branch = config.get("github_branch", "main")
    commit_message = config.get("commit_message", f"SEO plugin: update {file_path}")

    if not token or not repo:
        raise ValueError("github_token and github_repo are required for GitHub deployment")
    
    logger.info(f"GitHub Deploy: repo={repo}, branch={branch}, file={file_path}")

    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # Check if file exists to get its SHA
    sha = None
    with httpx.Client() as client:
        try:
            # Try direct GET first
            existing = client.get(api_url, headers=headers, params={"ref": branch})
            if existing.status_code == 200:
                sha = existing.json().get("sha")
            elif existing.status_code == 404:
                # Fallback: Check parent directory if file is in root or subdir
                parent_path = str(Path(file_path).parent).replace("\\", "/")
                if parent_path == ".":
                    parent_path = ""
                
                parent_url = f"https://api.github.com/repos/{repo}/contents/{parent_path}"
                logger.info(f"File 404'd, checking parent listing: {parent_url}")
                dir_res = client.get(parent_url, headers=headers, params={"ref": branch})
                if dir_res.status_code == 200:
                    for item in dir_res.json():
                        if item["name"].lower() == Path(file_path).name.lower():
                            sha = item["sha"]
                            logger.info(f"Found SHA via parent listing: {sha}")
                            break
            else:
                logger.warning(f"Unexpected status checking file existence: {existing.status_code} - {existing.text}")
        except Exception as e:
            logger.warning(f"Error checking file existence: {e}")

        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {
            "message": commit_message,
            "content": encoded,
            "branch": branch
        }
        if sha:
            payload["sha"] = sha

        response = client.put(api_url, headers=headers, json=payload)
        if response.status_code >= 400:
            err_msg = f"GitHub API error {response.status_code}: {response.text}"
            logger.error(err_msg)
            return {
                "success": False,
                "platform": "github",
                "file_path": file_path,
                "repo": repo,
                "branch": branch,
                "message": err_msg
            }

    return {
        "success": True,
        "platform": "github",
        "file_path": file_path,
        "repo": repo,
        "branch": branch,
        "message": "Committed successfully"
    }


# ─────────────────────────────────────────────────────────
# FTP
# ─────────────────────────────────────────────────────────

def _deploy_ftp(file_path: str, content: str, config: dict) -> dict:
    import ftplib
    from io import BytesIO

    host = config.get("ftp_host", "")
    user = config.get("ftp_user", "")
    password = config.get("ftp_password", "")
    base_dir = config.get("ftp_base_dir", "/public_html")

    remote_path = f"{base_dir}/{file_path}"

    with ftplib.FTP(host) as ftp:
        ftp.login(user, password)

        # Ensure directory exists
        parts = remote_path.split("/")[:-1]
        current = ""
        for part in parts:
            if not part:
                continue
            current += f"/{part}"
            try:
                ftp.mkd(current)
            except ftplib.error_perm:
                pass  # already exists

        ftp.storbinary(f"STOR {remote_path}", BytesIO(content.encode("utf-8")))

    return {
        "success": True,
        "platform": "ftp",
        "file_path": remote_path,
        "message": "Uploaded via FTP"
    }


# ─────────────────────────────────────────────────────────
# WEBHOOK
# ─────────────────────────────────────────────────────────

def _deploy_webhook(file_path: str, content: str, config: dict) -> dict:
    import httpx

    webhook_url = config.get("webhook_url", "")
    webhook_token = config.get("webhook_token", "")

    if not webhook_url:
        raise ValueError("webhook_url is required for webhook deployment")

    headers = {"Content-Type": "application/json"}
    if webhook_token:
        headers["Authorization"] = f"Bearer {webhook_token}"

    payload = {
        "file_path": file_path,
        "content": content
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(webhook_url, json=payload, headers=headers)
        response.raise_for_status()

    return {
        "success": True,
        "platform": "webhook",
        "file_path": file_path,
        "message": f"Webhook responded: {response.status_code}"
    }


# ─────────────────────────────────────────────────────────
# VERCEL DEPLOYMENTS API
# ─────────────────────────────────────────────────────────

# Vercel collects ALL files, then creates ONE deployment.
# We accumulate files in a class-level buffer and flush on demand.

_vercel_file_buffer: list = []


def vercel_add_file(file_path: str, content: str):
    """Buffer a file for a batch Vercel deployment."""
    _vercel_file_buffer.append({"file": file_path, "data": content})


def vercel_flush_deploy(config: dict) -> dict:
    """Create a single Vercel deployment with all buffered files."""
    import httpx

    token = config.get("vercel_token", "")
    project_id = config.get("vercel_project_id", "")
    team_id = config.get("vercel_team_id")

    if not token or not project_id:
        raise ValueError("vercel_token and vercel_project_id are required")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Build the files array for Vercel
    files = []
    for entry in _vercel_file_buffer:
        encoded = base64.b64encode(entry["data"].encode("utf-8")).decode("utf-8")
        files.append({
            "file": entry["file"],
            "data": encoded,
            "encoding": "base64"
        })

    payload = {
        "name": project_id,
        "files": files,
        "projectSettings": {
            "framework": None  # static deployment
        }
    }

    params = {}
    if team_id:
        params["teamId"] = team_id

    with httpx.Client(timeout=60) as client:
        response = client.post(
            "https://api.vercel.com/v13/deployments",
            headers=headers,
            json=payload,
            params=params
        )
        response.raise_for_status()
        result = response.json()

    _vercel_file_buffer.clear()

    return {
        "success": True,
        "platform": "vercel",
        "deployment_url": result.get("url", ""),
        "deployment_id": result.get("id", ""),
        "message": f"Deployed to Vercel: https://{result.get('url', '')}"
    }


def _deploy_vercel(file_path: str, content: str, config: dict) -> dict:
    """
    Buffer the file. For Vercel, we collect all files and deploy them in one
    batch at the end. The caller (plugin_runner) calls vercel_flush_deploy()
    after all files are buffered.
    """
    vercel_add_file(file_path, content)
    return {
        "success": True,
        "platform": "vercel",
        "file_path": file_path,
        "message": "File buffered for Vercel deployment"
    }


# ─────────────────────────────────────────────────────────
# HOSTINGER (SFTP via paramiko)
# ─────────────────────────────────────────────────────────

def _deploy_hostinger(file_path: str, content: str, config: dict) -> dict:
    import paramiko
    from io import BytesIO

    host = config.get("hostinger_host", "")
    username = config.get("hostinger_user", "")
    api_key = config.get("hostinger_api_key", "")  # used as SSH password or key passphrase
    site_id = config.get("hostinger_site_id", "")
    base_dir = config.get("hostinger_base_dir", f"/home/{username}/public_html")

    if not host or not username:
        raise ValueError("hostinger_host and hostinger_user are required for Hostinger SFTP deployment")

    remote_path = f"{base_dir}/{file_path}"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Try password-based auth with the API key
        ssh.connect(hostname=host, username=username, password=api_key, timeout=15)

        sftp = ssh.open_sftp()

        # Ensure remote directory exists
        dirs = remote_path.rsplit("/", 1)[0]
        _sftp_mkdir_p(sftp, dirs)

        # Upload the file
        file_obj = BytesIO(content.encode("utf-8"))
        sftp.putfo(file_obj, remote_path)

        sftp.close()
        logger.info("Hostinger SFTP: uploaded %s", remote_path)

    finally:
        ssh.close()

    return {
        "success": True,
        "platform": "hostinger",
        "file_path": remote_path,
        "site_id": site_id,
        "message": "Uploaded via Hostinger SFTP"
    }


def _sftp_mkdir_p(sftp, remote_dir):
    """Recursively create directories on the remote server."""
    if remote_dir == "/" or remote_dir == "":
        return
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parent = remote_dir.rsplit("/", 1)[0]
        _sftp_mkdir_p(sftp, parent)
        try:
            sftp.mkdir(remote_dir)
        except IOError:
            pass  # race condition or already exists
