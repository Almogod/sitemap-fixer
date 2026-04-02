from pydantic import BaseModel, HttpUrl, Field, SecretStr
from typing import Optional, List, Dict, Any

class BaseCrawlRequest(BaseModel):
    limit: int = Field(50, ge=1, le=10000)
    max_depth: int = Field(10, ge=1, le=100)
    crawl_assets: bool = False
    crawler_backend: str = Field("memory", pattern="^(memory|sqlite)$")
    concurrency: int = Field(10, ge=1, le=100)
    custom_selectors: Optional[Dict[str, str]] = None
    task_id: Optional[str] = None

class GenerateRequest(BaseCrawlRequest):
    domain: str # Standard URL or domain
    use_js: bool = False
    delay: float = Field(1.0, ge=0.1, le=30.0)
    check_robots: bool = True
    generate_sitemap: bool = True
    broken_links_only: bool = False

class PluginRunRequest(BaseCrawlRequest):
    site_url: str
    competitors: Optional[List[str]] = None
    openai_key: Optional[SecretStr] = None
    gemini_key: Optional[SecretStr] = None
    ollama_host: Optional[str] = "http://localhost:11434"
    site_token: Optional[SecretStr] = None

class DeployConfig(BaseModel):
    platform: str = "github"
    github_token: Optional[SecretStr] = None
    github_repo: Optional[str] = None
    github_branch: Optional[str] = "main"
    vercel_token: Optional[SecretStr] = None
    vercel_project_id: Optional[str] = None
    vercel_team_id: Optional[str] = None
    hostinger_api_key: Optional[SecretStr] = None
    hostinger_host: Optional[str] = None
    hostinger_user: Optional[str] = None
    hostinger_site_id: Optional[str] = None
    ftp_host: Optional[str] = None
    ftp_user: Optional[str] = None
    ftp_pass: Optional[SecretStr] = None
    webhook_url: Optional[str] = None

class PluginApproveRequest(BaseModel):
    task_id: str
    approved_actions: List[str] = []
    approved_pages: List[str] = []
    method: str = "github"
    deploy_config: Optional[DeployConfig] = None
    site_token: Optional[SecretStr] = None

class KeywordGenerationRequest(BaseModel):
    task_id: str
    keyword: str
    competitors: Optional[List[str]] = None
    openai_key: Optional[str] = None
    gemini_key: Optional[str] = None
    ollama_host: Optional[str] = None

class ContentUpdateRequest(BaseModel):
    task_id: str
    keyword: str
    schema_data: str
